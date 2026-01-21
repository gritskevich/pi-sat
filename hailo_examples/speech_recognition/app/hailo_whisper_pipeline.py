import numpy as np
import os
from hailo_platform import (HEF, VDevice, HailoSchedulingAlgorithm, FormatType)
from transformers import AutoTokenizer
from queue import Queue, Empty
from threading import Thread
from common.postprocessing import apply_repetition_penalty

try:
    from modules.logging_utils import setup_logger, log_info, log_warning
except Exception:  # Fallback for standalone use
    import logging
    def setup_logger(name, debug=False, verbose=True):
        return logging.getLogger(name)
    def log_info(logger, message):
        logger.info(message)
    def log_warning(logger, message):
        logger.warning(message)

logger = setup_logger(__name__)


class HailoWhisperPipeline:
    """
    A pipeline for running inference using Hailo's Whisper models.
    """

    def __init__(self, encoder_model_path: str, decoder_model_path: str, variant="tiny", host="arm64", multi_process_service=False, language="en"):
        """
        Initialize the pipeline.

        :param encoder_model_path: Path to the encoder model file.
        :param decoder_model_path: Path to the decoder model file.
        :param variant: Model variant (e.g., "tiny").
        :param language: Language code for transcription (e.g., "en", "fr", "es").
        """
        self.encoder_model_path = encoder_model_path
        self.decoder_model_path = decoder_model_path
        self.timeout_ms = 100000000
        self.variant = variant
        self.language = language

        self.decoding_sequence_length = None  # set from HEF
        self.host = host  # not used in this version
        self.multi_process_service = multi_process_service

        # Token embedding
        self.token_embedding_weight = self._load_token_embedding_weight()
        self.onnx_add_input = self._load_onnx_add_input()

        self.constant_output_0 = np.array([1])  # Unsqueeze axis
        self._load_tokenizer()

        # Get language token ID from tokenizer
        self.language_token_id = self._get_language_token_id()
        # Force transcription (avoid implicit translation-to-English on multilingual audio)
        self.transcribe_token_id = self._get_token_id("<|transcribe|>")
        self.no_timestamps_token_id = self._get_token_id("<|notimestamps|>")

        self.data_queue = Queue()
        self.results_queue = Queue()
        self.running = True
        self.thread = Thread(target=self._inference_loop)
        self.thread.start()

    def _load_token_embedding_weight(self):
        """
        Load token embedding weights.
        """
        base_path = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(base_path,
                                 f"decoder_assets/{self.variant}/decoder_tokenization/token_embedding_weight_{self.variant}.npy")
        return np.load(file_path)

    def _load_onnx_add_input(self):
        """
        Load ONNX add input.
        """
        base_path = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(base_path,
                                 f"decoder_assets/{self.variant}/decoder_tokenization/onnx_add_input_{self.variant}.npy")
        return np.load(file_path)

    def _load_tokenizer(self):
        """
        Load the tokenizer for the specified variant.
        """
        self.tokenizer = AutoTokenizer.from_pretrained(f"openai/whisper-{self.variant}")

    def _get_language_token_id(self):
        """
        Get the language token ID from the tokenizer.

        :return: Language token ID (integer)
        """
        language_token = f"<|{self.language}|>"
        token_id = self.tokenizer.convert_tokens_to_ids(language_token)

        # If token not found, default to English
        if token_id == self.tokenizer.unk_token_id:
            log_warning(logger, f"Language '{self.language}' not found in tokenizer, defaulting to English")
            token_id = self.tokenizer.convert_tokens_to_ids("<|en|>")

        return token_id

    def _get_token_id(self, token: str) -> int:
        token_id = self.tokenizer.convert_tokens_to_ids(token)
        if token_id == self.tokenizer.unk_token_id:
            log_warning(logger, f"Token '{token}' not found in tokenizer; disabling it")
            return None
        return token_id

    def _tokenization(self, decoder_input_ids):
        """
        Perform tokenization operations.

        :param decoder_input_ids: Input token IDs for the decoder.
        :return: Transposed tokenized output.
        """
        # embedding lookup
        gather_output = self.token_embedding_weight[decoder_input_ids]  # Shape: (len(decoder_input_ids), 384)
        # Add bias
        add_output = gather_output + self.onnx_add_input  # Broadcasting with shape (32, 384)
        # insert dimension at axis=1
        unsqueeze_output = np.expand_dims(add_output, axis=int(self.constant_output_0[0]))  # Shape: (32, 1, 384)
        # Transpose (0, 3, 2, 1) + turn into NHWC (0, 2, 3, 1)
        transpose_output = np.transpose(unsqueeze_output, (0, 2, 1, 3))

        return transpose_output

    def _inference_loop(self):
        """
        Main inference loop for processing input data and generating transcriptions.
        """
        params = VDevice.create_params()
        params.scheduling_algorithm = HailoSchedulingAlgorithm.ROUND_ROBIN
        
        if self.multi_process_service:
            params.multi_process_service = True
            params.group_id = "SHARED"

        # get output info
        decoder_hef = HEF(self.decoder_model_path)
        sorted_output_names = decoder_hef.get_sorted_output_names()
        decoder_model_name = decoder_hef.get_network_group_names()[0]
        self.decoding_sequence_length = decoder_hef.get_output_vstream_infos()[0].shape[1]

        encoder_hef = HEF(self.encoder_model_path)
        input_audio_length = int(encoder_hef.get_input_vstream_infos()[0].shape[1] / 100)
        log_info(
            logger,
            f"HailoWhisper variant={self.variant} input_len_s={input_audio_length} "
            f"decode_len={self.decoding_sequence_length}",
        )

        with VDevice(params) as vdevice:
            encoder_infer_model = vdevice.create_infer_model(self.encoder_model_path)
            decoder_infer_model = vdevice.create_infer_model(self.decoder_model_path)
            encoder_infer_model.input().set_format_type(FormatType.FLOAT32)
            encoder_infer_model.output().set_format_type(FormatType.FLOAT32)
            decoder_infer_model.input(f"{decoder_model_name}/input_layer1").set_format_type(FormatType.FLOAT32)
            decoder_infer_model.input(f"{decoder_model_name}/input_layer2").set_format_type(FormatType.FLOAT32)

            # model's outputs will be concatenated on the host
            for output_name in sorted_output_names:
                decoder_infer_model.output(output_name).set_format_type(FormatType.FLOAT32)


            with encoder_infer_model.configure() as encoder_configured_infer_model:
                with decoder_infer_model.configure() as decoder_configured_infer_model:
                    encoder_bindings = encoder_configured_infer_model.create_bindings()
                    decoder_bindings = decoder_configured_infer_model.create_bindings()

                    while self.running:
                        try:
                            # Wait for new data with a timeout to allow clean exit
                            input_mel = self.data_queue.get(timeout=1)

                            transcriptions = []
                            input_mel = np.ascontiguousarray(input_mel)
                            encoder_bindings.input().set_buffer(input_mel)
                            buffer = np.zeros(encoder_infer_model.output().shape).astype(np.float32)
                            encoder_bindings.output().set_buffer(buffer)

                            encoder_configured_infer_model.run([encoder_bindings], self.timeout_ms)
                            encoded_features = encoder_bindings.output().get_buffer()

                            # Decoder
                            # Whisper SOT sequence:
                            # <|startoftranscript|> + <|lang|> + <|transcribe|> + <|notimestamps|>
                            start_token_id = 50258
                            prefix_tokens = [start_token_id, self.language_token_id]
                            if self.transcribe_token_id is not None:
                                prefix_tokens.append(self.transcribe_token_id)
                            if self.no_timestamps_token_id is not None:
                                prefix_tokens.append(self.no_timestamps_token_id)

                            decoder_input_ids = np.zeros((1, self.decoding_sequence_length), dtype=np.int64)
                            decoder_input_ids[0, :len(prefix_tokens)] = np.array(prefix_tokens, dtype=np.int64)

                            generated_tokens = []
                            decoder_outputs = None
                            # Run Decoder Iteratively
                            prefix_len = len(prefix_tokens)
                            for i in range(self.decoding_sequence_length - prefix_len):
                                tokenized_ids = self._tokenization(decoder_input_ids)

                                decoder_bindings.input(f"{decoder_model_name}/input_layer1").set_buffer(encoded_features)
                                decoder_bindings.input(f"{decoder_model_name}/input_layer2").set_buffer(tokenized_ids)

                                buffers = [
                                    np.zeros(decoder_infer_model.output(name).shape).astype(np.float32) for name in sorted_output_names
                                ]

                                for name, buffer in zip(sorted_output_names, buffers):
                                    decoder_bindings.output(name).set_buffer(buffer)

                                decoder_configured_infer_model.run([decoder_bindings], self.timeout_ms)  # run decoder

                                decoder_outputs = np.concatenate(
                                    [decoder_bindings.output(name).get_buffer() for name in sorted_output_names], axis=2
                                )


                                # Decoder post-processing
                                repetition_penalty = 1.5
                                # Causal LM: logits at position t predict token at position t+1.
                                logits_index = (prefix_len - 1) + i
                                logits = apply_repetition_penalty(
                                    decoder_outputs[:, logits_index],
                                    generated_tokens,
                                    penalty=repetition_penalty
                                )
                                next_token = np.argmax(logits)
                                #else:
                                #   next_token = np.argmax(decoder_outputs[0][:, i])

                                generated_tokens.append(next_token)
                                decoder_input_ids[0][i + prefix_len] = np.array([[next_token]], dtype=np.int64)

                                if next_token == self.tokenizer.eos_token_id:
                                    break

                            # Convert token IDs to text
                            transcription = self.tokenizer.decode(
                                generated_tokens, skip_special_tokens=True
                            )
                            self.results_queue.put(transcription)
                            transcriptions.append(transcription)
                        except Empty:
                            pass  # No data yet, continue looping

    def send_data(self, data):
        """
        Send new data to the queue.

        :param data: Input data to process.
        """
        self.data_queue.put(data)

    def get_transcription(self):
        """
        Retrieve the next transcription result.

        :return: Transcription result.
        """
        return self.results_queue.get()

    def stop(self):
        """
        Stop the processing loop.
        """
        self.running = False
        self.thread.join()
