#!/usr/bin/env python3
"""Generate test report PDF with proper formatting"""

html_content = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        @page {
            size: A4;
            margin: 1cm;
        }
        body {
            font-family: 'Noto Color Emoji', 'DejaVu Sans', Arial, sans-serif;
            font-size: 8.5pt;
            line-height: 1.2;
            margin: 0;
            padding: 0;
        }
        h1 {
            text-align: center;
            font-size: 14pt;
            margin: 0 0 5px 0;
            color: #2c3e50;
        }
        h2 {
            font-size: 10pt;
            margin: 5px 0 3px 0;
            padding: 2px 6px;
            background: #3498db;
            color: white;
            border-radius: 3px;
        }
        h3 {
            font-size: 8.5pt;
            margin: 4px 0 2px 0;
            color: #555;
        }
        .header-info {
            display: flex;
            justify-content: space-between;
            margin-bottom: 4px;
            font-size: 8pt;
        }
        .instructions {
            background: #ecf0f1;
            padding: 5px;
            margin-bottom: 5px;
            border-radius: 3px;
            font-size: 8pt;
        }
        .instructions ol {
            margin: 3px 0;
            padding-left: 18px;
        }
        .instructions li {
            margin: 1px 0;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 2px 0 3px 0;
            font-size: 8pt;
        }
        th {
            background: #95a5a6;
            color: white;
            padding: 2px 3px;
            text-align: left;
            font-weight: bold;
        }
        td {
            border: 1px solid #bdc3c7;
            padding: 2px 3px;
        }
        .checkbox {
            text-align: center;
            font-size: 11pt;
        }
        .comment-box {
            border: 1px solid #bdc3c7;
            min-height: 15px;
            margin: 2px 0 4px 0;
            padding: 2px;
            background: white;
        }
        .section {
            margin-bottom: 5px;
        }
        .feedback-section {
            margin-top: 5px;
            padding: 4px;
            background: #fff9e6;
            border-radius: 3px;
        }
        .feedback-box {
            border: 1px solid #bdc3c7;
            min-height: 18px;
            margin: 2px 0;
            padding: 2px;
            background: white;
        }
        .rating {
            text-align: center;
            font-size: 18pt;
            margin: 4px 0;
        }
        .note {
            font-size: 7pt;
            color: #7f8c8d;
            font-style: italic;
        }
        hr {
            border: none;
            border-top: 1px solid #34495e;
            margin: 4px 0;
        }
    </style>
</head>
<body>
    <h1>🎵 MISSION TEST MUSICALE 🎵</h1>

    <div class="header-info">
        <div><strong>Testeuse:</strong> ____________________</div>
        <div><strong>Date:</strong> ___/___/2025</div>
    </div>

    <hr>

    <div class="instructions">
        <h3>📋 Comment ça marche ?</h3>
        <ol>
            <li>Dis <strong>"Alexa"</strong> (le mot magique !)</li>
            <li>Attends le <strong>BIP</strong> 🔊</li>
            <li>Donne ta commande (sans re-dire "Alexa")</li>
            <li>Pi-Sat t'obéit !</li>
        </ol>
        <p class="note"><strong>ASTUCE:</strong> Tu peux chercher une chanson par <strong>titre</strong> OU par <strong>artiste</strong> !</p>
    </div>

    <h2>✅ TESTS À FAIRE (fais chaque commande 2 fois minimum !)</h2>

    <div class="section">
        <h3>🎼 JOUER UNE CHANSON</h3>
        <table>
            <tr>
                <th style="width: 8%;">Essai</th>
                <th style="width: 60%;">Commande</th>
                <th style="width: 16%;" class="checkbox">✓ OK</th>
                <th style="width: 16%;" class="checkbox">✗ KO</th>
            </tr>
            <tr><td>1</td><td>"Je voudrais écouter [nom de chanson]"</td><td class="checkbox">☐</td><td class="checkbox">☐</td></tr>
            <tr><td>2</td><td>"Tu peux mettre [nom de chanson]"</td><td class="checkbox">☐</td><td class="checkbox">☐</td></tr>
            <tr><td>3</td><td>"Joue [nom de chanson]"</td><td class="checkbox">☐</td><td class="checkbox">☐</td></tr>
            <tr><td>4</td><td>"Mets de la musique de [nom d'artiste]"</td><td class="checkbox">☐</td><td class="checkbox">☐</td></tr>
            <tr><td>5</td><td>"Lance [nom d'artiste]"</td><td class="checkbox">☐</td><td class="checkbox">☐</td></tr>
        </table>
        <div class="comment-box"></div>
    </div>

    <div class="section">
        <h3>🔊 VOLUME PLUS FORT</h3>
        <table>
            <tr>
                <th style="width: 8%;">Essai</th>
                <th style="width: 60%;">Commande</th>
                <th style="width: 16%;" class="checkbox">✓ OK</th>
                <th style="width: 16%;" class="checkbox">✗ KO</th>
            </tr>
            <tr><td>1</td><td>"Plus fort"</td><td class="checkbox">☐</td><td class="checkbox">☐</td></tr>
            <tr><td>2</td><td>"Monte le volume"</td><td class="checkbox">☐</td><td class="checkbox">☐</td></tr>
            <tr><td>3</td><td>"Augmente le son"</td><td class="checkbox">☐</td><td class="checkbox">☐</td></tr>
        </table>
        <div class="comment-box"></div>
    </div>

    <div class="section">
        <h3>🔉 VOLUME MOINS FORT</h3>
        <table>
            <tr>
                <th style="width: 8%;">Essai</th>
                <th style="width: 60%;">Commande</th>
                <th style="width: 16%;" class="checkbox">✓ OK</th>
                <th style="width: 16%;" class="checkbox">✗ KO</th>
            </tr>
            <tr><td>1</td><td>"Moins fort"</td><td class="checkbox">☐</td><td class="checkbox">☐</td></tr>
            <tr><td>2</td><td>"Baisse le volume"</td><td class="checkbox">☐</td><td class="checkbox">☐</td></tr>
            <tr><td>3</td><td>"Diminue le son"</td><td class="checkbox">☐</td><td class="checkbox">☐</td></tr>
        </table>
        <div class="comment-box"></div>
    </div>

    <div class="section">
        <h3>⏹️ ARRÊTER LA MUSIQUE</h3>
        <table>
            <tr>
                <th style="width: 8%;">Essai</th>
                <th style="width: 60%;">Commande</th>
                <th style="width: 16%;" class="checkbox">✓ OK</th>
                <th style="width: 16%;" class="checkbox">✗ KO</th>
            </tr>
            <tr><td>1</td><td>"Stop"</td><td class="checkbox">☐</td><td class="checkbox">☐</td></tr>
            <tr><td>2</td><td>"Arrête"</td><td class="checkbox">☐</td><td class="checkbox">☐</td></tr>
            <tr><td>3</td><td>"Stop la musique"</td><td class="checkbox">☐</td><td class="checkbox">☐</td></tr>
            <tr><td>4</td><td>"Pause"</td><td class="checkbox">☐</td><td class="checkbox">☐</td></tr>
        </table>
        <div class="comment-box"></div>
    </div>

    <div class="feedback-section">
        <h3>💡 TES SUGGESTIONS D'AMÉLIORATION</h3>
        <strong>Ce qui marche super bien:</strong>
        <div class="feedback-box"></div>
        <strong>Ce qui ne marche pas bien:</strong>
        <div class="feedback-box"></div>
        <strong>Mes idées pour améliorer:</strong>
        <div class="feedback-box"></div>
    </div>

    <div style="text-align: center; margin-top: 4px;">
        <h3 style="margin: 2px 0;">⭐ NOTE GLOBALE</h3>
        <div class="rating">☐ ☐ ☐ ☐ ☐</div>
        <p style="font-size: 7pt; margin: 2px 0;">(colorie les étoiles !)</p>
        <p style="font-size: 10pt; font-weight: bold; margin: 4px 0;">MERCI CHEF TESTEUSE ! 🚀</p>
    </div>
</body>
</html>
"""

if __name__ == "__main__":
    try:
        from weasyprint import HTML
        HTML(string=html_content).write_pdf('rapport_test_musique.pdf')
        print("✅ PDF généré: rapport_test_musique.pdf")
    except ImportError:
        print("❌ weasyprint non installé. Installation...")
        print("Exécutez: pip install weasyprint")
        # Save HTML as fallback
        with open('rapport_test_musique.html', 'w', encoding='utf-8') as f:
            f.write(html_content)
        print("✅ HTML généré: rapport_test_musique.html")
