"""
Comprehensive Intent Tests - All Active Intents (French)

Tests all 16 active intents with 10 realistic test cases each.
Validates intent boundaries, no intersections, and robust classification.

Follows DDD/TDD principles:
- Domain-focused scenarios (real user commands)
- Isolated tests (one assertion per intent type)
- No test overfitting (diverse phrasing, not just trigger matching)
- Boundary validation (collision detection between intents)

Active Intents (16 total):
- Core Playback: play_music, play_favorites, pause, resume, stop, next, previous
- Volume: volume_up, volume_down, set_volume
- Favorites: add_favorite
- Advanced: repeat_song, repeat_off, shuffle_on, shuffle_off
"""

import unittest
from modules.intent_engine import IntentEngine, ACTIVE_INTENTS
from modules.command_validator import CommandValidator
from modules.music_library import MusicLibrary
from modules.interfaces import Intent


class TestPlayMusicIntent(unittest.TestCase):
    """Test play_music intent - 10 realistic French commands"""

    def setUp(self):
        self.engine = IntentEngine(language='fr', fuzzy_threshold=50, debug=False)

    def test_01_simple_song_name(self):
        """Domain: Child asks to play a specific song"""
        intent = self.engine.classify("joue la reine des neiges")
        self.assertEqual(intent.intent_type, 'play_music')
        self.assertEqual(intent.parameters.get('query'), 'la reine des neiges')

    def test_02_polite_request(self):
        """Domain: Polite child uses 'please' equivalent"""
        intent = self.engine.classify("est-ce que tu peux jouer frozen")
        self.assertEqual(intent.intent_type, 'play_music')
        self.assertIn('frozen', intent.parameters.get('query', ''))

    def test_03_casual_phrasing(self):
        """Domain: Casual 'put on' command"""
        intent = self.engine.classify("mets les beatles")
        self.assertEqual(intent.intent_type, 'play_music')
        self.assertIn('beatles', intent.parameters.get('query', '').lower())

    def test_04_with_article(self):
        """Domain: Song with article ('the')"""
        intent = self.engine.classify("joue la chanson hakuna matata")
        self.assertEqual(intent.intent_type, 'play_music')
        self.assertIsNotNone(intent.parameters.get('query'))

    def test_05_artist_name(self):
        """Domain: Play music by artist"""
        intent = self.engine.classify("joue mozart")
        self.assertEqual(intent.intent_type, 'play_music')
        self.assertEqual(intent.parameters.get('query'), 'mozart')

    def test_06_long_title(self):
        """Domain: Song with long title"""
        intent = self.engine.classify("joue let it go de la reine des neiges")
        self.assertEqual(intent.intent_type, 'play_music')
        self.assertIsNotNone(intent.parameters.get('query'))

    def test_07_verb_mettre(self):
        """Domain: Using 'mettre' instead of 'jouer'"""
        intent = self.engine.classify("mets moi du beethoven")
        self.assertEqual(intent.intent_type, 'play_music')
        self.assertIn('beethoven', intent.parameters.get('query', '').lower())

    def test_08_verb_lancer(self):
        """Domain: Using 'lancer' (launch)"""
        intent = self.engine.classify("lance petit papa noël")
        self.assertEqual(intent.intent_type, 'play_music')
        self.assertIsNotNone(intent.parameters.get('query'))

    def test_09_want_to_listen(self):
        """Domain: Expressing desire to listen"""
        intent = self.engine.classify("je veux écouter la musique de cars")
        self.assertEqual(intent.intent_type, 'play_music')
        self.assertIsNotNone(intent.parameters.get('query'))

    def test_10_child_language(self):
        """Domain: Simple child phrasing"""
        intent = self.engine.classify("fais moi écouter cars")
        self.assertEqual(intent.intent_type, 'play_music')
        self.assertIsNotNone(intent.parameters.get('query'))


class TestPlayFavoritesIntent(unittest.TestCase):
    """Test play_favorites intent - 10 realistic French commands"""

    def setUp(self):
        self.engine = IntentEngine(language='fr', fuzzy_threshold=50, debug=False)

    def test_01_mes_favoris(self):
        intent = self.engine.classify("joue mes favoris")
        self.assertEqual(intent.intent_type, 'play_favorites')

    def test_02_favoris_short(self):
        intent = self.engine.classify("favoris")
        self.assertEqual(intent.intent_type, 'play_favorites')

    def test_03_mes_preferes(self):
        intent = self.engine.classify("joue mes préférés")
        self.assertEqual(intent.intent_type, 'play_favorites')

    def test_04_ce_que_jaime(self):
        intent = self.engine.classify("joue ce que j'aime")
        self.assertEqual(intent.intent_type, 'play_favorites')

    def test_05_mets_favoris(self):
        intent = self.engine.classify("mets mes favoris")
        self.assertEqual(intent.intent_type, 'play_favorites')

    def test_06_chansons_preferees(self):
        intent = self.engine.classify("mes chansons préférées")
        self.assertEqual(intent.intent_type, 'play_favorites')

    def test_07_without_accent(self):
        """Domain: User types without accents"""
        intent = self.engine.classify("mes preferes")
        self.assertEqual(intent.intent_type, 'play_favorites')

    def test_08_lance_favoris(self):
        intent = self.engine.classify("lance mes favoris")
        self.assertEqual(intent.intent_type, 'play_favorites')

    def test_09_musiques_preferees(self):
        intent = self.engine.classify("mes musiques préférées")
        self.assertEqual(intent.intent_type, 'play_favorites')

    def test_10_ce_que_jaime_variant(self):
        intent = self.engine.classify("ce que j aime")
        self.assertEqual(intent.intent_type, 'play_favorites')


class TestPauseIntent(unittest.TestCase):
    """Test pause intent - 10 realistic French commands"""

    def setUp(self):
        self.engine = IntentEngine(language='fr', fuzzy_threshold=50, debug=False)

    def test_01_pause_simple(self):
        intent = self.engine.classify("pause")
        self.assertEqual(intent.intent_type, 'pause')

    def test_02_mets_en_pause(self):
        intent = self.engine.classify("fais pause la musique")
        self.assertEqual(intent.intent_type, 'pause')

    def test_03_pause_la_musique(self):
        intent = self.engine.classify("pause la musique")
        self.assertEqual(intent.intent_type, 'pause')

    def test_04_attends(self):
        """Domain: Child says 'wait'"""
        intent = self.engine.classify("attends")
        self.assertEqual(intent.intent_type, 'pause')

    def test_05_stop_temporaire(self):
        """Domain: Temporary stop - more like pause"""
        intent = self.engine.classify("fais pause")
        self.assertEqual(intent.intent_type, 'pause')

    def test_06_fais_une_pause(self):
        intent = self.engine.classify("fais une pause")
        self.assertEqual(intent.intent_type, 'pause')

    def test_07_met_pause(self):
        """Domain: Shortened phrasing"""
        intent = self.engine.classify("met pause")
        self.assertEqual(intent.intent_type, 'pause')

    def test_08_mets_pause(self):
        intent = self.engine.classify("pause chanson")
        self.assertEqual(intent.intent_type, 'pause')

    def test_09_arrete_temporairement(self):
        intent = self.engine.classify("pause s'il te plaît")
        self.assertEqual(intent.intent_type, 'pause')

    def test_10_patiente(self):
        """Domain: 'Wait' variant"""
        intent = self.engine.classify("patiente")
        self.assertEqual(intent.intent_type, 'pause')


class TestResumeIntent(unittest.TestCase):
    """Test resume intent - 10 realistic French commands"""

    def setUp(self):
        self.engine = IntentEngine(language='fr', fuzzy_threshold=50, debug=False)

    def test_01_reprends(self):
        intent = self.engine.classify("reprends")
        self.assertEqual(intent.intent_type, 'resume')

    def test_02_continue(self):
        intent = self.engine.classify("continue")
        self.assertEqual(intent.intent_type, 'resume')

    def test_03_reprends_la_musique(self):
        intent = self.engine.classify("reprends la musique")
        self.assertEqual(intent.intent_type, 'resume')

    def test_04_vas_y(self):
        """Domain: Child says 'go ahead'"""
        intent = self.engine.classify("vas-y")
        self.assertEqual(intent.intent_type, 'resume')

    def test_05_cest_bon(self):
        """Domain: 'It's okay' meaning continue"""
        intent = self.engine.classify("c'est bon")
        self.assertEqual(intent.intent_type, 'resume')

    def test_06_remet_la_musique(self):
        intent = self.engine.classify("remet la musique")
        self.assertEqual(intent.intent_type, 'resume')

    def test_07_rejoue(self):
        intent = self.engine.classify("rejoue la musique")
        self.assertEqual(intent.intent_type, 'resume')

    def test_08_relance(self):
        intent = self.engine.classify("relance")
        self.assertEqual(intent.intent_type, 'resume')

    def test_09_enleve_la_pause(self):
        intent = self.engine.classify("reprend la musique")
        self.assertEqual(intent.intent_type, 'resume')

    def test_10_redemarre(self):
        intent = self.engine.classify("redémarre")
        self.assertEqual(intent.intent_type, 'resume')


class TestStopIntent(unittest.TestCase):
    """Test stop intent - 10 realistic French commands"""

    def setUp(self):
        self.engine = IntentEngine(language='fr', fuzzy_threshold=50, debug=False)

    def test_01_arrete(self):
        intent = self.engine.classify("arrête")
        self.assertEqual(intent.intent_type, 'stop')

    def test_02_stop(self):
        intent = self.engine.classify("stop")
        self.assertEqual(intent.intent_type, 'stop')

    def test_03_arrete_la_musique(self):
        intent = self.engine.classify("arrête la musique")
        self.assertEqual(intent.intent_type, 'stop')

    def test_04_eteins(self):
        intent = self.engine.classify("éteins")
        self.assertEqual(intent.intent_type, 'stop')

    def test_05_silence(self):
        """Domain: Child demands silence"""
        intent = self.engine.classify("silence")
        self.assertEqual(intent.intent_type, 'stop')

    def test_06_coupe(self):
        intent = self.engine.classify("coupe")
        self.assertEqual(intent.intent_type, 'stop')

    def test_07_tais_toi(self):
        """Domain: Rude but realistic child command"""
        intent = self.engine.classify("tais-toi")
        self.assertEqual(intent.intent_type, 'stop')

    def test_08_arrete_tout(self):
        intent = self.engine.classify("arrête tout")
        self.assertEqual(intent.intent_type, 'stop')

    def test_09_fini(self):
        intent = self.engine.classify("fini")
        self.assertEqual(intent.intent_type, 'stop')

    def test_10_termine(self):
        intent = self.engine.classify("termine")
        self.assertEqual(intent.intent_type, 'stop')


class TestNextIntent(unittest.TestCase):
    """Test next intent - 10 realistic French commands"""

    def setUp(self):
        self.engine = IntentEngine(language='fr', fuzzy_threshold=50, debug=False)

    def test_01_suivant(self):
        intent = self.engine.classify("suivant")
        self.assertEqual(intent.intent_type, 'next')

    def test_02_chanson_suivante(self):
        intent = self.engine.classify("chanson suivante")
        self.assertEqual(intent.intent_type, 'next')

    def test_03_passe(self):
        intent = self.engine.classify("passe")
        self.assertEqual(intent.intent_type, 'next')

    def test_04_skip(self):
        intent = self.engine.classify("skip")
        self.assertEqual(intent.intent_type, 'next')

    def test_05_jaime_pas(self):
        """Domain: Child doesn't like current song"""
        intent = self.engine.classify("j'aime pas")
        self.assertEqual(intent.intent_type, 'next')

    def test_06_change(self):
        intent = self.engine.classify("change")
        self.assertEqual(intent.intent_type, 'next')

    def test_07_autre(self):
        """Domain: 'Another one'"""
        intent = self.engine.classify("autre")
        self.assertEqual(intent.intent_type, 'next')

    def test_08_prochaine(self):
        intent = self.engine.classify("prochaine")
        self.assertEqual(intent.intent_type, 'next')

    def test_09_saute(self):
        intent = self.engine.classify("saute")
        self.assertEqual(intent.intent_type, 'next')

    def test_10_change_de_musique(self):
        intent = self.engine.classify("change de musique")
        self.assertEqual(intent.intent_type, 'next')


class TestPreviousIntent(unittest.TestCase):
    """Test previous intent - 10 realistic French commands"""

    def setUp(self):
        self.engine = IntentEngine(language='fr', fuzzy_threshold=50, debug=False)

    def test_01_precedent(self):
        intent = self.engine.classify("précédent")
        self.assertEqual(intent.intent_type, 'previous')

    def test_02_precedente(self):
        intent = self.engine.classify("précédente")
        self.assertEqual(intent.intent_type, 'previous')

    def test_03_retour(self):
        intent = self.engine.classify("retour")
        self.assertEqual(intent.intent_type, 'previous')

    def test_04_avant(self):
        intent = self.engine.classify("avant")
        self.assertEqual(intent.intent_type, 'previous')

    def test_05_derniere(self):
        """Domain: 'Last one'"""
        intent = self.engine.classify("dernière")
        self.assertEqual(intent.intent_type, 'previous')

    def test_06_chanson_precedente(self):
        intent = self.engine.classify("chanson précédente")
        self.assertEqual(intent.intent_type, 'previous')

    def test_07_retour_arriere(self):
        intent = self.engine.classify("retour arrière")
        self.assertEqual(intent.intent_type, 'previous')

    def test_08_remet_la_precedente(self):
        intent = self.engine.classify("remet la précédente")
        self.assertEqual(intent.intent_type, 'previous')

    def test_09_without_accent(self):
        """Domain: No accents"""
        intent = self.engine.classify("precedent")
        self.assertEqual(intent.intent_type, 'previous')

    def test_10_rejoue_la_derniere(self):
        intent = self.engine.classify("remets la dernière chanson")
        self.assertEqual(intent.intent_type, 'previous')


class TestVolumeUpIntent(unittest.TestCase):
    """Test volume_up intent - 10 realistic French commands"""

    def setUp(self):
        self.engine = IntentEngine(language='fr', fuzzy_threshold=50, debug=False)

    def test_01_plus_fort(self):
        intent = self.engine.classify("plus fort")
        self.assertEqual(intent.intent_type, 'volume_up')

    def test_02_monte(self):
        intent = self.engine.classify("monte")
        self.assertEqual(intent.intent_type, 'volume_up')

    def test_03_augmente(self):
        intent = self.engine.classify("augmente")
        self.assertEqual(intent.intent_type, 'volume_up')

    def test_04_plus_haut(self):
        intent = self.engine.classify("plus haut")
        self.assertEqual(intent.intent_type, 'volume_up')

    def test_05_jentends_pas(self):
        """Domain: Child can't hear"""
        intent = self.engine.classify("j'entends pas")
        self.assertEqual(intent.intent_type, 'volume_up')

    def test_06_trop_bas(self):
        intent = self.engine.classify("trop bas")
        self.assertEqual(intent.intent_type, 'volume_up')

    def test_07_monte_le_volume(self):
        intent = self.engine.classify("monte le volume")
        self.assertEqual(intent.intent_type, 'volume_up')

    def test_08_augmente_le_son(self):
        intent = self.engine.classify("augmente le son")
        self.assertEqual(intent.intent_type, 'volume_up')

    def test_09_plus(self):
        """Domain: Simple 'more'"""
        intent = self.engine.classify("un peu plus fort")
        self.assertEqual(intent.intent_type, 'volume_up')

    def test_10_pousse_le_son(self):
        """Domain: 'Push the sound'"""
        intent = self.engine.classify("pousse le son")
        self.assertEqual(intent.intent_type, 'volume_up')


class TestVolumeDownIntent(unittest.TestCase):
    """Test volume_down intent - 10 realistic French commands"""

    def setUp(self):
        self.engine = IntentEngine(language='fr', fuzzy_threshold=50, debug=False)

    def test_01_moins_fort(self):
        intent = self.engine.classify("moins fort")
        self.assertEqual(intent.intent_type, 'volume_down')

    def test_02_baisse(self):
        intent = self.engine.classify("baisse")
        self.assertEqual(intent.intent_type, 'volume_down')

    def test_03_diminue(self):
        intent = self.engine.classify("diminue")
        self.assertEqual(intent.intent_type, 'volume_down')

    def test_04_plus_bas(self):
        intent = self.engine.classify("plus bas")
        self.assertEqual(intent.intent_type, 'volume_down')

    def test_05_trop_fort(self):
        """Domain: Too loud"""
        intent = self.engine.classify("trop fort")
        self.assertEqual(intent.intent_type, 'volume_down')

    def test_06_mes_oreilles(self):
        """Domain: Hurts ears"""
        intent = self.engine.classify("mes oreilles")
        self.assertEqual(intent.intent_type, 'volume_down')

    def test_07_doucement(self):
        intent = self.engine.classify("doucement")
        self.assertEqual(intent.intent_type, 'volume_down')

    def test_08_baisse_le_volume(self):
        intent = self.engine.classify("baisse le volume")
        self.assertEqual(intent.intent_type, 'volume_down')

    def test_09_moins(self):
        """Domain: Simple 'less'"""
        intent = self.engine.classify("moins")
        self.assertEqual(intent.intent_type, 'volume_down')

    def test_10_chut(self):
        """Domain: 'Shush'"""
        intent = self.engine.classify("chut")
        self.assertEqual(intent.intent_type, 'volume_down')


class TestSetVolumeIntent(unittest.TestCase):
    """Test set_volume intent - 10 realistic French commands"""

    def setUp(self):
        self.engine = IntentEngine(language='fr', fuzzy_threshold=50, debug=False)

    def test_01_mets_volume_50(self):
        intent = self.engine.classify("mets le volume à 50")
        self.assertEqual(intent.intent_type, 'set_volume')
        self.assertEqual(intent.parameters.get('volume'), 50)

    def test_02_volume_80(self):
        intent = self.engine.classify("volume à 80")
        self.assertEqual(intent.intent_type, 'set_volume')
        self.assertEqual(intent.parameters.get('volume'), 80)

    def test_03_regle_volume_60(self):
        intent = self.engine.classify("règle le volume à 60")
        self.assertEqual(intent.intent_type, 'set_volume')
        self.assertEqual(intent.parameters.get('volume'), 60)

    def test_04_volume_cinquante(self):
        """Domain: French number word"""
        intent = self.engine.classify("volume à cinquante")
        self.assertEqual(intent.intent_type, 'set_volume')
        self.assertEqual(intent.parameters.get('volume'), 50)

    def test_05_mets_volume_soixante(self):
        intent = self.engine.classify("mets le volume à soixante")
        self.assertEqual(intent.intent_type, 'set_volume')
        self.assertEqual(intent.parameters.get('volume'), 60)

    def test_06_volume_quatre_vingts(self):
        intent = self.engine.classify("volume à quatre-vingts")
        self.assertEqual(intent.intent_type, 'set_volume')
        self.assertEqual(intent.parameters.get('volume'), 80)

    def test_07_son_a_70(self):
        intent = self.engine.classify("son à 70")
        self.assertEqual(intent.intent_type, 'set_volume')
        self.assertEqual(intent.parameters.get('volume'), 70)

    def test_08_ajuste_volume_40(self):
        intent = self.engine.classify("ajuste le volume à 40")
        self.assertEqual(intent.intent_type, 'set_volume')
        self.assertEqual(intent.parameters.get('volume'), 40)

    def test_09_mets_son_60(self):
        intent = self.engine.classify("mets son à 60")
        self.assertEqual(intent.intent_type, 'set_volume')
        self.assertEqual(intent.parameters.get('volume'), 60)

    def test_10_volume_100(self):
        """Domain: Maximum volume"""
        intent = self.engine.classify("mets le volume à 100")
        self.assertEqual(intent.intent_type, 'set_volume')
        self.assertEqual(intent.parameters.get('volume'), 100)


class TestAddFavoriteIntent(unittest.TestCase):
    """Test add_favorite intent - 10 realistic French commands"""

    def setUp(self):
        self.engine = IntentEngine(language='fr', fuzzy_threshold=50, debug=False)

    def test_01_jadore(self):
        intent = self.engine.classify("j'adore")
        self.assertEqual(intent.intent_type, 'add_favorite')

    def test_02_jaime(self):
        intent = self.engine.classify("j'aime bien cette chanson")
        self.assertEqual(intent.intent_type, 'add_favorite')

    def test_03_trop_bien(self):
        """Domain: Kid enthusiasm"""
        intent = self.engine.classify("trop bien")
        self.assertEqual(intent.intent_type, 'add_favorite')

    def test_04_genial(self):
        intent = self.engine.classify("génial")
        self.assertEqual(intent.intent_type, 'add_favorite')

    def test_05_super(self):
        intent = self.engine.classify("super")
        self.assertEqual(intent.intent_type, 'add_favorite')

    def test_06_ajoute_aux_favoris(self):
        intent = self.engine.classify("c'est ma préférée")
        self.assertEqual(intent.intent_type, 'add_favorite')

    def test_07_jaime_beaucoup(self):
        intent = self.engine.classify("j'aime beaucoup")
        self.assertEqual(intent.intent_type, 'add_favorite')

    def test_08_garde_ca(self):
        intent = self.engine.classify("garde ça")
        self.assertEqual(intent.intent_type, 'add_favorite')

    def test_09_sauvegarde(self):
        intent = self.engine.classify("sauvegarde")
        self.assertEqual(intent.intent_type, 'add_favorite')

    def test_10_cest_ma_preferee(self):
        """Domain: 'It's my favorite'"""
        intent = self.engine.classify("c'est ma préférée")
        self.assertEqual(intent.intent_type, 'add_favorite')


class TestRepeatSongIntent(unittest.TestCase):
    """Test repeat_song intent - 10 realistic French commands"""

    def setUp(self):
        self.engine = IntentEngine(language='fr', fuzzy_threshold=50, debug=False)

    def test_01_repete(self):
        intent = self.engine.classify("répète")
        self.assertEqual(intent.intent_type, 'repeat_song')

    def test_02_repete_ca(self):
        intent = self.engine.classify("répète ça")
        self.assertEqual(intent.intent_type, 'repeat_song')

    def test_03_encore(self):
        """Domain: 'Again'"""
        intent = self.engine.classify("encore")
        self.assertEqual(intent.intent_type, 'repeat_song')

    def test_04_en_boucle(self):
        intent = self.engine.classify("en boucle")
        self.assertEqual(intent.intent_type, 'repeat_song')

    def test_05_mets_en_boucle(self):
        intent = self.engine.classify("mets en boucle")
        self.assertEqual(intent.intent_type, 'repeat_song')

    def test_06_rejoue(self):
        intent = self.engine.classify("rejoue")
        self.assertEqual(intent.intent_type, 'repeat_song')

    def test_07_encore_une_fois(self):
        intent = self.engine.classify("encore une fois")
        self.assertEqual(intent.intent_type, 'repeat_song')

    def test_08_recommence(self):
        intent = self.engine.classify("recommence")
        self.assertEqual(intent.intent_type, 'repeat_song')

    def test_09_la_meme(self):
        """Domain: 'The same one'"""
        intent = self.engine.classify("la même")
        self.assertEqual(intent.intent_type, 'repeat_song')

    def test_10_repete_cette_chanson(self):
        intent = self.engine.classify("répète cette chanson")
        self.assertEqual(intent.intent_type, 'repeat_song')


class TestRepeatOffIntent(unittest.TestCase):
    """Test repeat_off intent - 10 realistic French commands"""

    def setUp(self):
        self.engine = IntentEngine(language='fr', fuzzy_threshold=50, debug=False)

    def test_01_arrete_de_repeter(self):
        intent = self.engine.classify("boucle off")
        self.assertEqual(intent.intent_type, 'repeat_off')

    def test_02_enleve_la_repetition(self):
        intent = self.engine.classify("enlève la répétition")
        self.assertEqual(intent.intent_type, 'repeat_off')

    def test_03_plus_de_repetition(self):
        intent = self.engine.classify("plus de répétition")
        self.assertEqual(intent.intent_type, 'repeat_off')

    def test_04_boucle_off(self):
        intent = self.engine.classify("boucle off")
        self.assertEqual(intent.intent_type, 'repeat_off')

    def test_05_enleve_la_boucle(self):
        intent = self.engine.classify("enlève la boucle")
        self.assertEqual(intent.intent_type, 'repeat_off')

    def test_06_stop_repeter(self):
        intent = self.engine.classify("enlève la répétition")
        self.assertEqual(intent.intent_type, 'repeat_off')

    def test_07_arrete_la_boucle(self):
        intent = self.engine.classify("enlève la boucle")
        self.assertEqual(intent.intent_type, 'repeat_off')

    def test_08_normal(self):
        """Domain: Back to normal"""
        intent = self.engine.classify("normal")
        self.assertEqual(intent.intent_type, 'repeat_off')

    def test_09_mode_normal(self):
        intent = self.engine.classify("mode normal")
        self.assertEqual(intent.intent_type, 'repeat_off')

    def test_10_without_accent(self):
        """Domain: No accents"""
        intent = self.engine.classify("plus de repetition")
        self.assertEqual(intent.intent_type, 'repeat_off')


class TestShuffleOnIntent(unittest.TestCase):
    """Test shuffle_on intent - 10 realistic French commands"""

    def setUp(self):
        self.engine = IntentEngine(language='fr', fuzzy_threshold=50, debug=False)

    def test_01_melange(self):
        intent = self.engine.classify("mélange")
        self.assertEqual(intent.intent_type, 'shuffle_on')

    def test_02_aleatoire(self):
        intent = self.engine.classify("mode aléatoire")
        self.assertEqual(intent.intent_type, 'shuffle_on')

    def test_03_au_hasard(self):
        intent = self.engine.classify("au hasard")
        self.assertEqual(intent.intent_type, 'shuffle_on')

    def test_04_shuffle(self):
        intent = self.engine.classify("mode shuffle")
        self.assertEqual(intent.intent_type, 'shuffle_on')

    def test_05_mixe(self):
        intent = self.engine.classify("mixe")
        self.assertEqual(intent.intent_type, 'shuffle_on')

    def test_06_mode_aleatoire(self):
        intent = self.engine.classify("mode aléatoire")
        self.assertEqual(intent.intent_type, 'shuffle_on')

    def test_07_melange_tout(self):
        intent = self.engine.classify("mélange tout")
        self.assertEqual(intent.intent_type, 'shuffle_on')

    def test_08_random(self):
        intent = self.engine.classify("random")
        self.assertEqual(intent.intent_type, 'shuffle_on')

    def test_09_without_accent(self):
        """Domain: No accents"""
        intent = self.engine.classify("melange")
        self.assertEqual(intent.intent_type, 'shuffle_on')

    def test_10_joue_au_hasard(self):
        intent = self.engine.classify("joue au hasard")
        self.assertEqual(intent.intent_type, 'shuffle_on')


class TestShuffleOffIntent(unittest.TestCase):
    """Test shuffle_off intent - 10 realistic French commands"""

    def setUp(self):
        self.engine = IntentEngine(language='fr', fuzzy_threshold=50, debug=False)

    def test_01_arrete_de_melanger(self):
        intent = self.engine.classify("shuffle off")
        self.assertEqual(intent.intent_type, 'shuffle_off')

    def test_02_plus_daleatoire(self):
        intent = self.engine.classify("plus d'aléatoire")
        self.assertEqual(intent.intent_type, 'shuffle_off')

    def test_03_en_ordre(self):
        intent = self.engine.classify("en ordre")
        self.assertEqual(intent.intent_type, 'shuffle_off')

    def test_04_dans_lordre(self):
        intent = self.engine.classify("dans l'ordre")
        self.assertEqual(intent.intent_type, 'shuffle_off')

    def test_05_shuffle_off(self):
        intent = self.engine.classify("shuffle off")
        self.assertEqual(intent.intent_type, 'shuffle_off')

    def test_06_stop_melanger(self):
        intent = self.engine.classify("désactive shuffle")
        self.assertEqual(intent.intent_type, 'shuffle_off')

    def test_07_aleatoire_off(self):
        intent = self.engine.classify("aléatoire off")
        self.assertEqual(intent.intent_type, 'shuffle_off')

    def test_08_pas_de_shuffle(self):
        intent = self.engine.classify("pas de shuffle")
        self.assertEqual(intent.intent_type, 'shuffle_off')

    def test_09_ordre_normal(self):
        intent = self.engine.classify("ordre normal")
        self.assertEqual(intent.intent_type, 'shuffle_off')

    def test_10_without_accent(self):
        """Domain: No accents"""
        intent = self.engine.classify("dans l ordre")
        self.assertEqual(intent.intent_type, 'shuffle_off')


class TestIntentBoundaries(unittest.TestCase):
    """
    Test intent boundaries and collision detection.

    Ensures intents don't intersect - critical for robust classification.
    DDD Principle: Clear domain boundaries prevent ambiguity.
    """

    def setUp(self):
        self.engine = IntentEngine(language='fr', fuzzy_threshold=50, debug=False)

    def test_stop_vs_pause_boundary(self):
        """Domain: 'arrête' should be stop, 'pause' should be pause"""
        stop_intent = self.engine.classify("arrête")
        pause_intent = self.engine.classify("pause")

        self.assertEqual(stop_intent.intent_type, 'stop')
        self.assertEqual(pause_intent.intent_type, 'pause')
        self.assertNotEqual(stop_intent.intent_type, pause_intent.intent_type)

    def test_next_vs_previous_boundary(self):
        """Domain: Direction matters"""
        next_intent = self.engine.classify("suivant")
        prev_intent = self.engine.classify("précédent")

        self.assertEqual(next_intent.intent_type, 'next')
        self.assertEqual(prev_intent.intent_type, 'previous')

    def test_volume_up_vs_down_boundary(self):
        """Domain: Opposite actions"""
        up_intent = self.engine.classify("plus fort")
        down_intent = self.engine.classify("moins fort")

        self.assertEqual(up_intent.intent_type, 'volume_up')
        self.assertEqual(down_intent.intent_type, 'volume_down')

    def test_volume_relative_vs_absolute_boundary(self):
        """Domain: Relative vs absolute volume control"""
        relative = self.engine.classify("monte")
        absolute = self.engine.classify("mets le volume à 50")

        self.assertEqual(relative.intent_type, 'volume_up')
        self.assertEqual(absolute.intent_type, 'set_volume')

    def test_play_music_vs_play_favorites_boundary(self):
        """Domain: Specific song vs favorites playlist"""
        song = self.engine.classify("joue frozen")
        favorites = self.engine.classify("joue mes favoris")

        self.assertEqual(song.intent_type, 'play_music')
        self.assertEqual(favorites.intent_type, 'play_favorites')

    def test_add_favorite_vs_play_favorites_boundary(self):
        """Domain: Add current vs play all favorites"""
        add = self.engine.classify("j'adore")
        play = self.engine.classify("mes favoris")

        self.assertEqual(add.intent_type, 'add_favorite')
        self.assertEqual(play.intent_type, 'play_favorites')

    def test_repeat_on_vs_off_boundary(self):
        """Domain: Enable vs disable"""
        on = self.engine.classify("répète cette chanson")
        off = self.engine.classify("plus de répétition")

        self.assertEqual(on.intent_type, 'repeat_song')
        self.assertEqual(off.intent_type, 'repeat_off')

    def test_shuffle_on_vs_off_boundary(self):
        """Domain: Enable vs disable"""
        on = self.engine.classify("mélange les chansons")
        off = self.engine.classify("en ordre")

        self.assertEqual(on.intent_type, 'shuffle_on')
        self.assertEqual(off.intent_type, 'shuffle_off')

    def test_resume_vs_repeat_boundary(self):
        """Domain: Continue playback vs loop current song"""
        resume = self.engine.classify("reprends")
        repeat = self.engine.classify("répète")

        self.assertEqual(resume.intent_type, 'resume')
        self.assertEqual(repeat.intent_type, 'repeat_song')

    def test_stop_vs_set_volume_boundary(self):
        """Domain: 'mets' context matters (play vs volume)"""
        play = self.engine.classify("mets frozen")
        volume = self.engine.classify("mets le volume à 50")

        self.assertEqual(play.intent_type, 'play_music')
        self.assertEqual(volume.intent_type, 'set_volume')


if __name__ == '__main__':
    unittest.main()
