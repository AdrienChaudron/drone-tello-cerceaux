"""Construit docs/rapport_E3_segmentation_couleur.pdf (ReportLab), meme plan que le rapport E2."""
import json
import os
import sys

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, Preformatted, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

OUT = sys.argv[1]
PDF = sys.argv[2]
R = json.load(open(os.path.join(OUT, "resultats.json")))
E3, E2 = R["E3"], R["E2"]

F = "/usr/share/fonts/truetype/dejavu/"
pdfmetrics.registerFont(TTFont("DV", F + "DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("DVB", F + "DejaVuSans-Bold.ttf"))
pdfmetrics.registerFont(TTFont("DVI", F + "DejaVuSans-Oblique.ttf"))
pdfmetrics.registerFont(TTFont("DVM", F + "DejaVuSansMono.ttf"))
from reportlab.pdfbase.pdfmetrics import registerFontFamily  # noqa: E402
registerFontFamily("DV", normal="DV", bold="DVB", italic="DVI", boldItalic="DVB")

ss = getSampleStyleSheet()
BLEU = colors.HexColor("#1f4e79")
N = ParagraphStyle("n", parent=ss["Normal"], fontName="DV", fontSize=9.5, leading=13.5, spaceAfter=5)
NC = ParagraphStyle("nc", parent=N, alignment=TA_CENTER)
CAP = ParagraphStyle("cap", parent=N, fontName="DVI", fontSize=8, leading=10.5, alignment=TA_CENTER, spaceAfter=9)
H1 = ParagraphStyle("h1", parent=N, fontName="DVB", fontSize=14, leading=18, textColor=BLEU, spaceBefore=10, spaceAfter=6)
H2 = ParagraphStyle("h2", parent=N, fontName="DVB", fontSize=11, leading=14, textColor=BLEU, spaceBefore=7, spaceAfter=4)
T = ParagraphStyle("t", parent=N, fontSize=8.2, leading=10.5, spaceAfter=0)
TB = ParagraphStyle("tb", parent=T, fontName="DVB", textColor=colors.white)
BUL = ParagraphStyle("b", parent=N, leftIndent=12, bulletIndent=2)
CODE = ParagraphStyle("code", parent=N, fontName="DVM", fontSize=7.6, leading=9.6, backColor=colors.HexColor("#f3f5f8"),
                      borderPadding=5, leftIndent=4, spaceBefore=3, spaceAfter=8)
BOX = ParagraphStyle("box", parent=N, backColor=colors.HexColor("#e8f0f8"), borderColor=BLEU, borderWidth=0.6,
                     borderPadding=7, spaceBefore=6, spaceAfter=10)
TITLE = ParagraphStyle("ti", parent=N, fontName="DVB", fontSize=24, leading=30, alignment=TA_CENTER, textColor=BLEU)
SUB = ParagraphStyle("su", parent=N, fontSize=11, leading=15, alignment=TA_CENTER)

S = []
P = lambda t, st=N: S.append(Paragraph(t, st))
B = lambda items: [S.append(Paragraph(i, BUL, bulletText="•")) for i in items]


def tab(rows, widths, head=True):
    data = [[Paragraph(str(c), TB if (head and i == 0) else T) for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=[w * cm for w in widths], repeatRows=1 if head else 0)
    st = [("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#b8c4d0")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if head:
        st.append(("BACKGROUND", (0, 0), (-1, 0), BLEU))
    for i in range(1, len(rows)):
        if i % 2 == 0:
            st.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f2f6fa")))
    t.setStyle(TableStyle(st))
    S.append(t)
    S.append(Spacer(1, 7))


def fig(name, width_cm, caption):
    from reportlab.lib.utils import ImageReader
    p = os.path.join(OUT, name)
    iw, ih = ImageReader(p).getSize()
    w = width_cm * cm
    S.append(KeepTogether([Image(p, width=w, height=w * ih / iw), Paragraph(caption, CAP)]))


def pc(x, d=1):
    return f"{100 * x:.{d}f} %".replace(".", ",")


def f(x, d=1):
    return f"{x:.{d}f}".replace(".", ",")


L3, L2 = E3["localisation"], E2["localisation"]
B3, B2 = E3["boites"], E2["boites"]
P3, P2 = E3["presence"], E2["presence"]
Q3, Q2 = E3["pose3d"], E2["pose3d"]
D = R["donnees"]
t3 = E3["t_cnn"] + E3["t_ell"] + E3["t_pose"]

# ------------------------------------------------------------------ page de titre
S.append(Spacer(1, 0.8 * cm))
P("Modèle E3", TITLE)
P("Segmentation de l'anneau insensible à la couleur<br/>et localisation 2D / 3D du cerceau", ParagraphStyle("t2", parent=TITLE, fontSize=16, leading=21))
S.append(Spacer(1, 0.6 * cm))
P("Résumé complet : pourquoi E3, données et augmentations de couleur, architecture du CNN, entraînement, meilleure "
  "époque, métriques comparées à E2, robustesse à la couleur, essais en vol avec le cerceau vert, passage du masque "
  "aux coordonnées 2D puis 3D", SUB)
S.append(Spacer(1, 0.5 * cm))
P("Partie vision du projet de vol autonome d'un drone Tello<br/>Modèle : logs/E3_segmentation480_couleur_0 · "
  "config : configs/E3_segmentation480_couleur.yaml<br/>code : ~/Documents/tello/tellovision · rapport du 14/10/2026", SUB)
S.append(Spacer(1, 0.2 * cm))

P("Fiche d'identité", H1)
tab([["Élément", "Valeur"],
     ["Nom de l'expérience", "E3_segmentation480_couleur (dossier logs/E3_segmentation480_couleur_0)"],
     ["Différence avec E2", "Une seule : trois augmentations de couleur à l'entraînement (teinte tournée sur tout le "
      "cercle, canaux permutés, niveaux de gris). Données, réseau, perte, réglages et validation identiques."],
     ["Pourquoi", "Un deuxième cerceau, vert, était mal détecté en vol : le réseau ne devait plus dépendre de la couleur."],
     ["Tâche", "Segmentation de l'anneau + présence, puis ajustement d'ellipse et pose 3D"],
     ["Modèle", "RingSegNet : encodeur MobileNetV3-small pré-entraîné (ImageNet) + décodeur U-Net"],
     ["Entrée / sortie", "Image 480×360 → masque 240×180 + probabilité de présence"],
     ["Paramètres", "1,67 million (encodeur 0,93 M, décodeur 0,74 M, tête de présence 577)"],
     ["Données", f"{D['train'] + D['valid']} images : {D['train']} d'entraînement ({D['train_cerceaux']} cerceaux, "
      f"{D['train'] - D['train_cerceaux']} vides), {D['valid']} de validation ({D['valid_cerceaux']} / "
      f"{D['valid'] - D['valid_cerceaux']})"],
     ["Meilleure époque", f"{E3['epoch']} (sur 36 effectuées, 0 à 35 ; arrêt anticipé après l'époque 35)"],
     ["Perte de validation retenue", "0,6827 (E2 : 0,7016)"],
     ["Présence (validation)", f"exactitude {pc(P3['exactitude'])}, précision {pc(P3['precision'])}, rappel "
      f"{pc(P3['rappel'])}, F1 {f(P3['F1'], 3)}, AP {f(P3['AP'], 3)}"],
     ["Boîte englobante (validation)", f"IoU médiane {f(B3['visible']['med'], 2)} ; {pc(B3['visible']['sup05'], 0)} des "
      f"images à IoU ≥ 0,5 ; AP@0,5 = {f(B3['AP50'], 2)} (E2 : {f(B2['AP50'], 2)})"],
     ["Centre 2D (validation)", f"médiane {f(L3['tout']['centre_med'])} px (cage : {f(L3['cage']['centre_med'])} px) ; "
      f"moyenne {f(L3['tout']['centre_moy'])} px"],
     ["Distance 3D", f"cage : erreur médiane {pc(Q3['cage']['dist_rel_med'])} ({f(100 * Q3['cage']['dist_abs_med'], 0)} cm) ; "
      f"couloir : {pc(Q3['couloir']['dist_rel_med'])} (E2 : {pc(Q2['couloir']['dist_rel_med'])})"],
     ["Robustesse à la couleur", "Validation recolorée (7 variantes) : 5 fausses alarmes sur 210 images vides pour E3, "
      "21 pour E2 ; rappel identique (94 à 98 %)"],
     ["Temps de calcul (CPU)", f"{f(t3, 0)} ms par image : CNN {f(E3['t_cnn'], 0)} ms + ellipse {f(E3['t_ell'], 0)} ms "
      f"+ pose {f(E3['t_pose'], 1)} ms (≈ 15 images/s)"],
     ["Verdict", "E3 remplace E2 en vol (vision_node, voir_mqtt, live_detect, detector par défaut)."]],
    [4.6, 12.4])
S.append(PageBreak())

# ------------------------------------------------------------------ 1
P("1. Pourquoi E3", H1)
P("E2 a été entraîné uniquement avec le cerceau violet de la cage (et quelques cerceaux gris du couloir). Son "
  "augmentation de couleur ne faisait varier la teinte que de ±4 unités OpenCV (±8° sur 360°) : le réseau pouvait "
  "donc s'appuyer sur la couleur du tube. Lors des essais du 14/10 avec un second cerceau, vert, la détection était "
  "difficile. Deux solutions : filmer et annoter le cerceau vert, ou rendre le réseau insensible à la couleur. E3 "
  "teste la seconde, qui ne demande aucune annotation.")
P("Principe : à l'entraînement, la couleur des images est changée au hasard (teinte, ordre des canaux, niveaux de "
  "gris). Le cerceau prend toutes les couleurs, le fond aussi ; la seule chose stable d'une image à l'autre est la "
  "forme de l'anneau. Tout le reste est identique à E2, ce qui permet une comparaison directe.")
tab([["Modèle (même validation stable)", "Présence", "Centre médian", "Grand axe médian", "B/A"],
     ["E0 – régression 320×240", "89,2 %", "68 px", "16,6 %", "0,082"],
     ["E1 – régression 480×360", "90,8 %", "78 px", "28,1 %", "0,086"],
     ["E2 – segmentation 480×360", pc(P2["exactitude"]), f"{f(L2['tout']['centre_med'])} px",
      pc(L2["tout"]["grand_axe_med"]), f(L2["tout"]["BA_moy"], 3)],
     ["E3 – segmentation 480×360, couleur", pc(P3["exactitude"]), f"{f(L3['tout']['centre_med'])} px",
      pc(L3["tout"]["grand_axe_med"]), f(L3["tout"]["BA_moy"], 3)]],
    [6.2, 2.2, 2.6, 3, 2])
P("E2 et E3 sont évalués ici avec exactement la même chaîne (même passage masque → ellipse, même validation) : les "
  "chiffres d'E2 de ce tableau sont ceux de son rapport.")

# ------------------------------------------------------------------ 2
P("2. Les données", H1)
P("2.1 Jeu de données et découpage", H2)
P("Inchangé par rapport à E2. 615 images de la caméra du Tello (960×720), prises dans le couloir (cerceaux gris, "
  "2,7 à 5,5 m) et dans la cage (cerceau violet de 68 cm, 0,9 à 3,1 m) : 374 avec cerceau, 241 vides. Règle "
  "d'annotation : si moins d'un tiers du cerceau est visible, l'image est vide. Chaque cerceau est annoté par une "
  "ellipse (centre, grand axe, petit axe, inclinaison), qui peut déborder de l'image.")
P(f"Découpage stable : chaque image appartient à une tranche de 5 s (horodatage du nom), et le côté de la tranche "
  f"est fixé par un hachage (CRC32) de son numéro avec la graine 0. Résultat : {D['train']} images d'entraînement "
  f"({D['train_cerceaux']} cerceaux, {D['train'] - D['train_cerceaux']} vides) et {D['valid']} de validation "
  f"({D['valid_cerceaux']} cerceaux dont {D['valid_cage']} de la cage et {D['valid_couloir']} du couloir, "
  f"{D['valid'] - D['valid_cerceaux']} vides). Aucune image du cerceau vert n'est dans ces données.")
P("2.2 Prétraitement", H2)
B(["redimensionnement en 480×360 (rapport 4:3 conservé) ;",
   "passage de BGR (OpenCV) à RGB, valeurs ramenées dans [0, 1] puis normalisées avec la moyenne (0,485 ; 0,456 ; "
   "0,406) et l'écart-type (0,229 ; 0,224 ; 0,225) d'ImageNet. Cette conversion est la même à l'entraînement, à la "
   "validation et en vol (detector.py) ;",
   "tenseur (canaux, hauteur, largeur) : un lot de 16 images est un tenseur (16, 3, 360, 480)."])
P("2.3 Le masque cible", H2)
P("Le réseau apprend à reproduire un masque de l'anneau, dessiné automatiquement à partir de l'ellipse annotée : "
  "l'ellipse est ramenée à la résolution du masque (240×180, pas de 2) et tracée avec une épaisseur de 4 % du "
  "diamètre (tube de 2,5 cm sur 68 cm), au minimum 2 pixels. Une image vide a un masque noir ; une « corde » (arc "
  "trop court) a un masque inconnu, ignoré par la perte.")
fig("fig1_masque.png", 13, "Figure 1 – Masque cible dessiné à partir de l'ellipse annotée.")
P("2.4 Augmentations (entraînement seulement)", H2)
tab([["Transformation", "Probabilité", "Paramètres", "Rôle"],
     ["Miroir horizontal", "0,5", "—", "Cerceau vu de l'autre côté"],
     ["Rotation de caméra H = K R K⁻¹", "0,6", "lacet ±12°, tangage ±8°, roulis ±12° ; K de la calibration",
      "Le drone tourne ; ellipse transformée exactement"],
     ["Zoom + décalage", "0,5", "échelle 0,6 à 1,3 ; décalage ±15 %", "Distance et position variées"],
     ["Visibilité minimale", "—", "au moins 34 % du contour dans l'image", "Cohérent avec la règle du tiers"],
     ["Couleur / lumière", "0,8", "luminosité ±35 %, contraste ±30 %, saturation ±40 %, teinte ±4", "Contre-jour, exposition"],
     ["<b>NOUVEAU – Teinte tournée</b>", "<b>0,5</b>", "teinte décalée d'une valeur tirée sur tout le cercle (0 à 360°)",
      "Cerceau vert, bleu, jaune… : la couleur ne renseigne plus"],
     ["<b>NOUVEAU – Canaux permutés</b>", "<b>0,3</b>", "ordre B, G, R tiré au hasard", "Autre façon de changer la couleur"],
     ["<b>NOUVEAU – Niveaux de gris</b>", "<b>0,2</b>", "image convertie en gris (3 canaux identiques)",
      "Reconnaître le cerceau à sa forme seule"],
     ["Flou de bougé", "0,3", "noyau ≤ 11 px", "Mouvement du drone"],
     ["Bruit", "0,3", "écart-type ≤ 8", "Capteur"],
     ["Rectangle masqué", "0,3", "côté ≤ 15 % de l'image", "Occultation"],
     ["Compression JPEG", "0,5", "qualité 35 à 80", "Flux Wi-Fi"],
     ["Collage sur un autre fond", "0", "désactivé", "Créait des anneaux « fantômes »"]],
    [4.2, 1.8, 6, 5])
P("Les trois nouvelles augmentations sont appliquées après la couleur / lumière, indépendamment les unes des "
  "autres : environ 72 % des images d'entraînement ont une couleur modifiée en plus du réglage de lumière. Elles sont "
  "codées dans tellovision/data.py (hue_rotate, channel_shuffle, grayscale) et désactivées si la configuration ne "
  "les mentionne pas : E0, E1 et E2 se réentraînent à l'identique. La validation n'a <b>aucune</b> augmentation.")
fig("fig2b_couleur.png", 16, "Figure 2 – Les trois augmentations de couleur sur une même image de la cage.")
fig("fig2_augmentations.png", 14, "Figure 3 – Exemples d'images d'entraînement d'E3 après augmentation : le cerceau "
    "violet apparaît rose, bleu, vert, blanc ou gris.")

# ------------------------------------------------------------------ 3
P("3. Le réseau RingSegNet", H1)
P("Identique à E2 (seuls les poids changent). Le réseau a la forme d'un U : un encodeur réduit l'image en cartes de "
  "caractéristiques de plus en plus abstraites et de moins en moins résolues ; un décodeur remonte la résolution en "
  "réutilisant les cartes de l'encodeur (connexions de saut) pour retrouver le détail fin du tube. Deux têtes "
  "répondent aux deux questions : y a-t-il un cerceau, et où est le tube.")
S.append(Preformatted(
    "image (3, 360, 480)\n"
    "  │ ENCODEUR MobileNetV3-small (pré-entraîné ImageNet)\n"
    "  ├─ bloc 0  ─► (16, 180, 240)  pas 2  ──────────────────────────┐\n"
    "  ├─ bloc 1  ─► (16, 90, 120)   pas 4  ─────────────────────┐    │\n"
    "  ├─ bloc 3  ─► (24, 45, 60)    pas 8  ────────────────┐    │    │\n"
    "  ├─ bloc 8  ─► (48, 23, 30)    pas 16 ───────────┐    │    │    │\n"
    "  └─ bloc 12 ─► (576, 12, 15)   pas 32            ▼    ▼    ▼    ▼\n"
    "        ├─ TÊTE DE PRÉSENCE : moyenne globale → 576 → Dropout 0,2 → Linear → 1 logit\n"
    "        └─ DÉCODEUR : up1 (96,23,30) → up2 (48,45,60) → up3 (32,90,120) → up4 (24,180,240)\n"
    "                      → Conv 1×1 → MASQUE (1, 180, 240) = logits « tube » par pixel", CODE))
P("3.1 L'encodeur : MobileNetV3-small", H2)
P("Réseau conçu pour les téléphones : peu de calculs, mais pré-entraîné sur 1,2 million d'images (ImageNet), il "
  "reconnaît déjà bords, textures et formes. Ses 13 blocs sont faits de :")
B(["une convolution d'entrée 3×3 de pas 2 (16 filtres), normalisation par lot, activation hard-swish (version "
   "rapide de x·sigmoïde(x)) ;",
   "blocs « résiduels inversés » : convolution 1×1 qui augmente le nombre de canaux, convolution en profondeur 3×3 ou "
   "5×5 (un filtre par canal), module squeeze-and-excitation (moyenne globale de chaque canal → petite couche dense "
   "→ poids qui renforcent les canaux utiles), convolution 1×1 de projection, connexion résiduelle quand les "
   "dimensions le permettent ;",
   "une convolution finale 1×1 vers 576 canaux (hard-swish)."])
P("La résolution est divisée par 2 cinq fois, par des convolutions de pas 2 (pas de max-pooling). On prélève les "
  "sorties des blocs 0, 1, 3, 8 et 12, aux pas 2, 4, 8, 16 et 32.")
P("3.2 Le décodeur U-Net", H2)
P("Chaque bloc de remontée (UpBlock) : interpolation bilinéaire jusqu'à la taille de la carte de l'encodeur "
  "correspondante, concaténation avec elle, puis deux fois (convolution 3×3 + normalisation par lot + ReLU). Une "
  "dernière convolution 1×1 produit un logit par pixel.")
tab([["Bloc", "Entrées (canaux)", "Sortie", "Paramètres"],
     ["up1", "576 (pas 32) + 48 (pas 16)", "(96, 23, 30)", "622 k"],
     ["up2", "96 + 24 (pas 8)", "(48, 45, 60)", "73 k"],
     ["up3", "48 + 16 (pas 4)", "(32, 90, 120)", "28 k"],
     ["up4", "32 + 16 (pas 2)", "(24, 180, 240)", "16 k"],
     ["Tête du masque", "Conv 1×1, 24 → 1", "(1, 180, 240)", "25"]], [3.5, 6, 4, 3])
P("3.3 La tête de présence (classification)", H2)
P("Moyenne globale de la carte la plus profonde (576×12×15 → 576 valeurs), Dropout de 0,2, puis une couche dense "
  "vers 1 logit ; la probabilité de présence est la sigmoïde de ce logit. La présence est une question globale : la "
  "position n'importe pas. Pour la localisation au contraire, toute l'information spatiale est gardée par le décodeur.")
tab([["Où", "Opération", "Rôle"],
     ["Encodeur (descente)", "Convolutions de pas 2", "Réduire la résolution, agrandir le champ réceptif"],
     ["Modules squeeze-and-excitation", "Moyenne globale par canal", "Pondérer les canaux"],
     ["Décodeur (remontée)", "Interpolation bilinéaire + connexions de saut", "Retrouver le détail fin"],
     ["Tête de présence", "Moyenne globale + Dropout 0,2", "Décision globale, limiter le surapprentissage"],
     ["Partout", "Normalisation par lot", "Stabiliser l'apprentissage"]], [4.5, 6, 6.5])

# ------------------------------------------------------------------ 4
P("4. La perte", H1)
S.append(Preformatted(
    "perte = BCE(présence)                 poids des positifs : 1\n"
    "      + 1 × BCE(masque) pondérée      poids des pixels « tube » : 10\n"
    "      + 1 × Dice(masque)              images contenant un anneau seulement\n"
    "(perte de masque ignorée pour les « cordes », dont le masque est inconnu)", CODE))
P("L'anneau n'occupe que quelques pour cent des pixels : avec une entropie croisée simple, prédire « fond » partout "
  "donnerait déjà une perte faible ; on multiplie donc par 10 le poids des pixels du tube. La perte de Dice mesure "
  "directement le recouvrement entre masque prédit P et masque vrai T : Dice = 1 − (2·Σ P·T + 1) / (Σ P + Σ T + 1). "
  "Elle vaut 0 pour un recouvrement parfait et ne dépend pas du nombre de pixels de fond. Inchangée par rapport à E2.")

# ------------------------------------------------------------------ 5
P("5. L'entraînement", H1)
tab([["Réglage", "Valeur"],
     ["Optimiseur", "AdamW, pas 10⁻³ pour le décodeur et les têtes, 10⁻⁴ pour l'encodeur (× 0,1), pénalité des poids 10⁻⁴"],
     ["Calendrier du pas", "Cosinus sur 50 époques : pas = pas initial × (1 + cos(π·époque/50)) / 2"],
     ["Lot", "16 images"],
     ["Nombre d'époques", "50 au maximum ; arrêt anticipé après 12 époques sans amélioration"],
     ["Choix du meilleur modèle", "Plus petite perte de validation"],
     ["Graine aléatoire", "0"],
     ["Matériel", "CPU (pas de GPU), environ 102 s par époque, 59 minutes au total (E2 : 80 s, 50 min) ; les "
      "conversions de couleur ajoutent un peu de travail au chargement des images"],
     ["Commande", "python -m tellovision.main configs/E3_segmentation480_couleur.yaml train"]], [4.5, 12.5])
fig("fig3_courbes.png", 17, "Figure 4 – Courbes d'apprentissage d'E3 (bleu) et d'E2 (gris). Le pointillé vertical "
    "marque l'époque retenue (23). Attention : les erreurs de centre d'E2 sur ce graphique ont été calculées pendant "
    "son entraînement avec la première version du passage masque → ellipse (§7), moins bonne ; elles ne sont pas "
    "comparables à celles d'E3. La comparaison juste est celle du §6, avec la même chaîne pour les deux.")
P(f"<b>Meilleure époque : 23</b>, avec une perte de validation de 0,6827 (E2 : 0,7016 à l'époque 25). Ensuite la "
  "perte de validation stagne (0,70 à 0,73) pendant que la perte d'entraînement continue de baisser (0,56 → 0,44) : "
  "le réseau commence à sur-apprendre, et l'arrêt anticipé s'est déclenché après l'époque 35. Le modèle enregistré est "
  "celui de l'époque 23, pas le dernier.")
P("Sur toute la fin de l'entraînement (époques 15 à 35), la perte de validation d'E3 reste sous celle d'E2 "
  "(moyenne 0,712 contre 0,735) : les augmentations de couleur jouent aussi un rôle de régularisation.")

# ------------------------------------------------------------------ 6
P("6. Métriques et résultats (validation stable, 120 images)", H1)
P("Toutes les mesures portent sur les 120 images de validation (90 avec cerceau, 30 sans), jamais vues pendant "
  "l'entraînement et séparées par tranches de 5 s pour éviter les quasi-doublons. E2 est recalculé avec la même "
  "chaîne pour comparaison ; ses chiffres retrouvent exactement ceux de son rapport.")
P("6.1 Définitions des métriques", H2)
P("<b>Présence (classification).</b> Le réseau donne une probabilité p ; on décide « cerceau » si p ≥ 0,5. Chaque "
  "image tombe dans une des quatre cases de la matrice de confusion :")
tab([["Case", "Signification", "Conséquence pour le drone"],
     ["VP (vrai positif)", "cerceau présent, détecté", "—"],
     ["FN (faux négatif)", "cerceau présent, raté", "le drone continue à chercher : perte de temps"],
     ["FP (faux positif)", "rien, mais cerceau annoncé", "le drone vise un objet qui n'existe pas : dangereux"],
     ["VN (vrai négatif)", "rien, et rien annoncé", "—"]], [3.5, 5.5, 8])
B(["<b>Exactitude</b> = (VP + VN) / total : part des images bien classées (trompeuse si les classes sont déséquilibrées, ici 90 / 30).",
   "<b>Précision</b> = VP / (VP + FP) : quand le modèle annonce un cerceau, peut-on le croire ? Métrique de sécurité.",
   "<b>Rappel</b> = VP / (VP + FN) : parmi les vrais cerceaux, combien sont trouvés ?",
   "<b>Spécificité</b> = VN / (VN + FP) : parmi les images vides, combien sont reconnues vides ?",
   "<b>F1</b> = 2 · précision · rappel / (précision + rappel).",
   "<b>AP</b> (average precision) : aire sous la courbe précision / rappel obtenue en faisant varier le seuil ; juge le "
   "modèle indépendamment du seuil (1 = parfait)."])
P("<b>Localisation.</b> Le recouvrement entre forme prédite et forme de référence se mesure par l'IoU (Intersection "
  "over Union) = aire commune / aire totale couverte (1 = identiques). On le calcule sur le masque (pixels « tube »), "
  "la boîte englobante et l'ellipse pleine. S'y ajoutent les erreurs utiles au vol : erreur du centre (px), erreur "
  "relative du grand axe (elle se transmet telle quelle à la distance), erreur du rapport B/A (orientation du "
  "cerceau) et erreur d'inclinaison de l'ellipse (degrés, ellipses aplaties B/A < 0,85).")
P("6.2 Présence", H2)
fig("fig4_presence.png", 17, "Figure 5 – Gauche : matrice de confusion d'E3 au seuil 0,5. Milieu : courbes précision "
    "/ rappel d'E3 et d'E2 (point rouge : seuil 0,5). Droite : IoU boîte et ellipse sur les 90 images avec cerceau "
    "(une image sans prédiction compte 0).")
tab([["Métrique", "E3", "E2", "Lecture (E3)"],
     ["Matrice de confusion", f"VP {P3['VP']} · FN {P3['FN']} · FP {P3['FP']} · VN {P3['VN']}",
      f"VP {P2['VP']} · FN {P2['FN']} · FP {P2['FP']} · VN {P2['VN']}", f"{P3['FN'] + P3['FP']} erreurs sur 120"],
     ["Exactitude", pc(P3["exactitude"]), pc(P2["exactitude"]), f"{P3['VP'] + P3['VN']} images sur 120"],
     ["Précision", pc(P3["precision"]), pc(P2["precision"]), "1 seule fausse alarme (la même image pour les deux)"],
     ["Rappel", pc(P3["rappel"]), pc(P2["rappel"]), f"{P3['FN']} cerceaux ratés"],
     ["Spécificité", pc(P3["specificite"]), pc(P2["specificite"]), "29 images vides sur 30"],
     ["F1", f(P3["F1"], 3), f(P2["F1"], 3), ""],
     ["AP (aire sous P/R)", f(P3["AP"], 3), f(P2["AP"], 3), "les probabilités classent presque parfaitement les images"]],
    [3.6, 3.7, 3.7, 6])
P(f"E3 rate un cerceau de moins qu'E2 ; les quatre cerceaux ratés le sont aussi par E2 (p = "
  f"{', '.join(f(x, 2) for x in P3['p_FN'])}) : deux cerceaux lointains du couloir et deux très coupés de la cage. "
  f"La seule fausse alarme est la même image vide du couloir pour les deux modèles, avec une probabilité plus basse "
  f"pour E3 ({f(P3['p_FP'][0], 2)} contre {f(P2['p_FP'][0], 2)}). Sur 1 ou 2 images, ces écarts restent dans le "
  "bruit : la détection est équivalente. En vol, la confirmation sur 5 images consécutives élimine en plus les "
  "fausses alarmes isolées.")
P("6.3 Localisation 2D", H2)
tab([["Mesure", "E3 toutes", "E3 cage", "E3 couloir", "E2 toutes", "E2 cage", "E2 couloir"],
     ["IoU du masque", f(E3["mask_iou_recalcule"], 2), "—", "—", f(E2["mask_iou_recalcule"], 2), "—", "—"],
     ["Centre 2D, médiane (px)", *[f(L3[z]["centre_med"]) for z in ("tout", "cage", "couloir")],
      *[f(L2[z]["centre_med"]) for z in ("tout", "cage", "couloir")]],
     ["Centre 2D, moyenne (px)", *[f(L3[z]["centre_moy"]) for z in ("tout", "cage", "couloir")],
      *[f(L2[z]["centre_moy"]) for z in ("tout", "cage", "couloir")]],
     ["Centres à plus de 50 px", *[str(L3[z]["centre_sup50"]) for z in ("tout", "cage", "couloir")],
      *[str(L2[z]["centre_sup50"]) for z in ("tout", "cage", "couloir")]],
     ["Grand axe (≈ distance), médiane", *[pc(L3[z]["grand_axe_med"]) for z in ("tout", "cage", "couloir")],
      *[pc(L2[z]["grand_axe_med"]) for z in ("tout", "cage", "couloir")]],
     ["Grand axe, moyenne", *[pc(L3[z]["grand_axe_moy"]) for z in ("tout", "cage", "couloir")],
      *[pc(L2[z]["grand_axe_moy"]) for z in ("tout", "cage", "couloir")]],
     ["Rapport B/A, erreur moyenne", *[f(L3[z]["BA_moy"], 3) for z in ("tout", "cage", "couloir")],
      *[f(L2[z]["BA_moy"], 3) for z in ("tout", "cage", "couloir")]],
     ["Inclinaison (ellipses aplaties), médiane",
      *[f"{f(L3[z]['incl_med'])}° ({L3[z]['n_incl']})" for z in ("tout", "cage", "couloir")],
      *[f"{f(L2[z]['incl_med'])}° ({L2[z]['n_incl']})" for z in ("tout", "cage", "couloir")]]],
    [4.4, 2.1, 2.1, 2.1, 2.1, 2.1, 2.1])
P("Lecture honnête : avec la même chaîne, <b>le centre 2D est équivalent</b> (9,7 contre 9,2 px en médiane ; dans "
  "la cage 4,9 contre 3,9 px, soit un pixel d'écart). E3 fait en revanche <b>moins de grosses erreurs</b> (8 centres "
  "à plus de 50 px contre 12), mesure mieux la <b>taille</b> (grand axe médian 3,0 % contre 3,9 %), la <b>forme</b> "
  "(B/A 0,074 contre 0,083) et surtout <b>l'orientation</b> des ellipses aplaties du couloir (28° contre 62°). Ce "
  "dernier point compte pour la pose 3D (§8.5).")
S.append(Paragraph("Correction d'une conclusion précédente. Pendant l'entraînement, TensorBoard montrait un écart "
                   "bien plus grand (centre moyen 19 contre 44 px, grand axe 12 contre 35 %). Cet écart venait surtout "
                   "de la version du passage masque → ellipse utilisée au moment de chaque entraînement : celle d'E2 "
                   "était l'ancienne. Avec la même chaîne, le gain réel d'E3 est celui de ce tableau.", BOX))
P("6.4 Boîtes englobantes", H2)
P("Une boîte englobante est le plus petit rectangle aligné sur les axes qui contient l'objet (x1, y1, x2, y2), la "
  "sortie des détecteurs classiques (YOLO, SSD, Faster R-CNN). E3, comme E2, ne prédit pas de boîte mais une ellipse "
  "(5 nombres : centre, deux demi-axes, angle), qui contient toute l'information de la boîte et en plus l'orientation "
  "du cerceau, indispensable à la pose 3D. La boîte s'en déduit (ellipse_bbox) : demi-largeur w = √(A²cos²θ + "
  "B²sin²θ), demi-hauteur h = √(A²sin²θ + B²cos²θ). La boîte de référence est déduite de la même façon de l'ellipse "
  "annotée, puis limitée au cadre de l'image.")
tab([["Métrique (90 images avec cerceau)", "E3 boîte visible", "E3 boîte amodale", "E3 ellipse pleine", "E2 boîte visible"],
     ["IoU moyen", f(B3["visible"]["moy"], 2), f(B3["amodale"]["moy"], 2), f(B3["ellipse"]["moy"], 2), f(B2["visible"]["moy"], 2)],
     ["IoU médian", f(B3["visible"]["med"], 2), f(B3["amodale"]["med"], 2), f(B3["ellipse"]["med"], 2), f(B2["visible"]["med"], 2)],
     ["Part des images à IoU ≥ 0,5", pc(B3["visible"]["sup05"], 0), pc(B3["amodale"]["sup05"], 0), pc(B3["ellipse"]["sup05"], 0), pc(B2["visible"]["sup05"], 0)],
     ["Part des images à IoU ≥ 0,75", pc(B3["visible"]["sup075"], 0), pc(B3["amodale"]["sup075"], 0), pc(B3["ellipse"]["sup075"], 0), pc(B2["visible"]["sup075"], 0)],
     ["AP@0,5 (style détecteur)", f(B3["AP50"], 2), "—", "—", f(B2["AP50"], 2)],
     ["AP@0,75", f(B3["AP75"], 2), "—", "—", f(B2["AP75"], 2)]], [5, 3, 3, 3, 3])
B(["<b>AP@0,5</b> : métrique classique des détecteurs (PASCAL VOC). Une détection est juste si p ≥ seuil et IoU de "
   "boîte ≥ 0,5 ; on trie les détections par probabilité et on calcule l'aire sous la courbe précision / rappel. "
   "AP@0,75 est la version exigeante.",
   "<b>Boîte amodale</b> : boîte de l'ellipse entière, partie hors image comprise (plus sévère).",
   f"E3 gagne nettement en AP@0,5 ({f(B3['AP50'], 2)} contre {f(B2['AP50'], 2)}) et en part d'images à IoU ≥ 0,5 "
   f"({pc(B3['visible']['sup05'], 0)} contre {pc(B2['visible']['sup05'], 0)}) : moins de cerceaux mal placés. Le pic de "
   "la distribution (figure 5, droite) est entre 0,9 et 1 ; les IoU nulles sont les 4 cerceaux ratés."])

# ------------------------------------------------------------------ 7
P("7. Du masque aux coordonnées 2D", H1)
fig("fig5_chaine.png", 17, "Figure 6 – La chaîne d'E3 sur une image de la cage. 2 : probabilité « tube » prédite. "
    "3 : zone retenue (jaune) et ellipse RANSAC (magenta). 4 : résultat final.")
P("7.1 Ajuster l'ellipse sur le masque", H2)
B(["<b>Seuil</b> : on garde les pixels de probabilité ≥ 0,5.",
   "<b>Plus grande zone connexe seulement</b> : les petites taches isolées sont du bruit.",
   "<b>Candidat A – RANSAC</b> : 150 fois, on tire 5 pixels, on ajuste une ellipse (cv2.fitEllipse) et on compte les "
   "pixels à moins de 4 % de son contour ; on garde la meilleure et on la réajuste sur ses pixels proches. Efficace "
   "quand le masque est un anneau ou un arc.",
   "<b>Candidat B – contour extérieur</b> : ellipse ajustée sur le bord extérieur de la zone, réduite d'une "
   "demi-épaisseur de tube. Efficace pour les petits cerceaux, dont le masque devient une tache pleine.",
   "<b>Choix</b> : la candidate qui passe sur les pixels les plus probables (probabilité moyenne sur 128 points de son contour).",
   "<b>Changement de repère</b> : du masque (240×180) à l'image (960×720), facteur 4 sur les centres de pixels."])
P("Limite vue en vol (§10) : quand la plus grande zone du masque n'est pas le cerceau (main, perche, manche sombre), "
  "l'ellipse est ajustée sur ce fragment et donne une ellipse plate, au mauvais endroit.")
P("7.2 Le centre 2D du cerceau n'est pas le centre de l'ellipse", H2)
P(f"Par la perspective, la moitié la plus proche du cerceau paraît plus grande : le centre de l'ellipse n'est pas "
  f"l'image du centre du cerceau. Le centre 2D renvoyé (u, v) est donc la projection du centre 3D (§8), distorsion "
  f"comprise. Dans la validation de la cage, l'écart vaut {f(Q3['cage']['ecart_centre_ellipse_med'])} px en médiane "
  f"et jusqu'à {f(Q3['cage']['ecart_centre_ellipse_max'], 0)} px, de près et de biais.")

# ------------------------------------------------------------------ 8
P("8. Des coordonnées 2D à la 3D", H1)
P("Cette partie géométrique est commune à E2 et E3 : elle ne dépend que de l'ellipse.")
P("8.1 La calibration de la caméra", H2)
tab([["Grandeur", "Valeur", "Sens"],
     ["Focales fx, fy", "927,1 et 925,8 px", "Conversion angle ↔ pixels"],
     ["Centre optique cx, cy", "475,8 ; 386,3 px", "Point de l'image dans l'axe de la caméra"],
     ["Distorsion k1, k2, p1, p2, k3", "−0,015 ; 0,035 ; 0,002 ; 0,002 ; 0,034", "Très faible"],
     ["Erreur de reprojection", "0,23 px sur 39 images de damier", "Très bonne calibration"],
     ["Champ de vision", "54,7° × 42,5° (65,9° en diagonale)", "Le flux 960×720 n'utilise que le centre du capteur"],
     ["Inclinaison de la caméra", "10,3° vers le bas (configs/drone.yaml)", "Passage repère caméra → repère drone"]],
    [4.5, 6, 6.5])
P("Avant le calcul, la distorsion est corrigée : 72 points du contour de l'ellipse sont redressés "
  "(cv2.undistortPoints) et l'ellipse est réajustée.")
P("8.2 Du cercle vu en ellipse au cercle 3D", H2)
P("Chaque point de l'ellipse correspond à un rayon issu de la caméra : ces rayons forment un cône. Si C est la "
  "matrice de la conique de l'ellipse (pixels) et K la matrice de la caméra, le cône a pour équation XᵀQX = 0 avec "
  "Q = KᵀCK. On diagonalise Q : valeurs propres λ1 ≥ λ2 > 0 > λ3, vecteurs propres en colonnes de V. Seuls deux plans "
  "coupent ce cône selon un cercle de rayon r = 0,34 m :")
S.append(Preformatted(
    "a = √((λ1 − λ2) / (λ1 − λ3))     b = √((λ2 − λ3) / (λ1 − λ3))     s = ±1 (deux solutions)\n"
    "normale  n = V · [ s·a, 0, −b ]\n"
    "centre   c = r / √(−λ1·λ3) · V · [ s·a·λ3, 0, −b·λ1 ]\n"
    "signes fixés pour que le cerceau soit devant la caméra (c_z > 0) et que la normale\n"
    "pointe dans le sens de la traversée (n_z > 0)", CODE))
P("Référence : Chen, Wu, Wada, « Camera calibration with two arbitrary coplanar circles », ECCV 2004. Vérification "
  "sur 500 cercles simulés : erreur maximale de 0,4 mm sur le centre et 0,13° sur la normale ; toute l'erreur finale "
  "vient du réseau. Attention : le diamètre (configs/hoop.yaml, 0,68 m) est celui du cerceau violet ; un cerceau vert "
  "de diamètre différent fausse toutes les distances dans le même rapport.")
P("8.3 Les grandeurs renvoyées", H2)
tab([["Grandeur", "Calcul", "Utilisation"],
     ["Centre 3D (x, y, z)", "c, en mètres ; x à droite, y vers le BAS, z devant", "Position du cerceau"],
     ["Repère drone (avant, droite, haut)", "c tourné de l'inclinaison de la caméra", "delta_z, distance envoyés au PC de contrôle"],
     ["Distance", "‖c‖", "Phase d'approche, passage en TRAVERSEE"],
     ["Centre 2D (u, v)", "projection de c par la calibration", "delta_x (pixels) envoyé au PC de contrôle"],
     ["Normale n", "vecteur unitaire, sens de la traversée", "Direction d'entrée"],
     ["Lacet vers la normale", "atan2(nx, nz)", "Se placer face au cerceau"],
     ["Angle de vue", "acos(nz)", "Écart à l'axe du cerceau"]], [4.5, 6.5, 6])
P("8.4 L'ambiguïté double", H2)
fig("fig6_ambiguite.png", 12.5, "Figure 7 – Frame 0459 avec E3 : les deux solutions ont le même centre (1,01 m) mais "
    "deux orientations, tournées de +29° et −44°.")
P("Une ellipse correspond à deux orientations possibles du cercle, comme une pièce tournée à gauche ou à droite. "
  "Règles de choix : (1) suivi d'une image à l'autre (normale la plus proche de la précédente) ; (2) sinon cerceau "
  "vertical, donc normale horizontale. Quand les deux restent proches, le résultat est marqué « ambigu ». "
  "L'ambiguïté disparaît quand le drone s'aligne (B/A = 1). En vol, la mise en axe actuelle n'utilise que le centre "
  "(delta_x, delta_z, distance), pas la normale : l'ambiguïté ne gêne pas le guidage.")
P("8.5 Précision 3D", H2)
P("Référence : la pose calculée à partir de l'ellipse annotée, comparée à celle calculée à partir de l'ellipse prédite.")
tab([["Mesure (médiane)", "E3 cage", "E2 cage", "E3 couloir", "E2 couloir"],
     ["Plage de distance", f"{f(Q3['cage']['dist_min'])} à {f(Q3['cage']['dist_max'])} m", "idem",
      f"{f(Q3['couloir']['dist_min'])} à {f(Q3['couloir']['dist_max'])} m", "idem"],
     ["Distance", f"{pc(Q3['cage']['dist_rel_med'])} ({f(100 * Q3['cage']['dist_abs_med'], 0)} cm)",
      f"{pc(Q2['cage']['dist_rel_med'])} ({f(100 * Q2['cage']['dist_abs_med'], 0)} cm)",
      f"{pc(Q3['couloir']['dist_rel_med'])} ({f(100 * Q3['couloir']['dist_abs_med'], 0)} cm)",
      f"{pc(Q2['couloir']['dist_rel_med'])} ({f(100 * Q2['couloir']['dist_abs_med'], 0)} cm)"],
     ["Centre 3D", f"{f(100 * Q3['cage']['centre3d_med'], 1)} cm, dont {f(100 * Q3['cage']['lateral_med'], 1)} cm latéralement",
      f"{f(100 * Q2['cage']['centre3d_med'], 1)} cm, dont {f(100 * Q2['cage']['lateral_med'], 1)} cm",
      f"{f(100 * Q3['couloir']['centre3d_med'], 0)} cm", f"{f(100 * Q2['couloir']['centre3d_med'], 0)} cm"],
     ["Centre 2D (u, v)", f"{f(Q3['cage']['centre2d_med'])} px", f"{f(Q2['cage']['centre2d_med'])} px",
      f"{f(Q3['couloir']['centre2d_med'])} px", f"{f(Q2['couloir']['centre2d_med'])} px"],
     ["Normale", f"{f(Q3['cage']['normale_med'])}° ({f(Q3['cage']['normale_p90'], 0)}° pour 10 % des cas)",
      f"{f(Q2['cage']['normale_med'])}° ({f(Q2['cage']['normale_p90'], 0)}°)",
      f"{f(Q3['couloir']['normale_med'], 0)}°", f"{f(Q2['couloir']['normale_med'], 0)}°"]],
    [3.4, 4, 3.2, 3.2, 3.2])
P("Dans la cage, E3 et E2 sont équivalents (distance à 1,6-1,7 %, soit 3 à 4 cm). Dans le couloir, plus loin et à "
  "contre-jour, E3 est nettement meilleur : distance 10 % au lieu de 16 % (33 cm au lieu de 44 cm), normale 24° au "
  "lieu de 32°. Les cas extrêmes de la normale dans la cage sont aussi réduits (19° contre 24° pour 10 % des cas).")
S.append(Paragraph("Limites à connaître pour le guidage. Près de l'axe du cerceau, B/A ≈ cos(angle de vue) varie très "
                   "peu : une erreur de 0,04 sur B/A laisse l'angle entre 0 et environ 16° ; en fin d'approche, mieux "
                   "vaut s'appuyer sur le centre que sur la normale. Le cerceau ne tient plus entièrement dans l'image "
                   "en dessous d'environ 0,87 m : le dernier mètre se fait à l'aveugle. Enfin, la caméra voit jusqu'à "
                   "environ 31° sous l'horizontale (21° de demi-champ + 10° d'inclinaison) : un cerceau nettement plus "
                   "bas que le drone sort de l'image par le bas pendant l'approche.", BOX))

# ------------------------------------------------------------------ 9
P("9. Robustesse à la couleur", H1)
P("Pour mesurer ce que les augmentations ont apporté sans images du cerceau vert, la validation est <b>recolorée</b> : "
  "la teinte de chaque image est décalée de 60 en 60° (le cerceau violet devient rouge, jaune, vert, cyan, bleu), "
  "convertie en gris, ou ses canaux B et R sont inversés. Les 120 images restent annotées : on mesure le rappel sur "
  "les 90 cerceaux et les fausses alarmes sur les 30 images vides, pour E2 et E3.")
fig("fig7_couleur.png", 17, "Figure 8 – Validation recolorée. Gauche : part des 90 cerceaux trouvés. Droite : fausses "
    "alarmes sur les 30 images vides.")
rows = [["Variante", "E2 rappel", "E2 fausses alarmes", "E2 centre méd.", "E3 rappel", "E3 fausses alarmes", "E3 centre méd."]]
for t in R["couleur"]["tests"]:
    if t["test"].startswith("cerceau vert"):
        continue
    rows.append([t["test"], pc(t["E2"]["rappel"]), f"{t['E2']['FP']} / 30", f"{f(t['E2']['centre_med'])} px",
                 pc(t["E3"]["rappel"]), f"{t['E3']['FP']} / 30", f"{f(t['E3']['centre_med'])} px"])
tab(rows, [3.4, 2.1, 2.5, 2.3, 2.1, 2.5, 2.3])
B(["<b>Le rappel ne bouge presque pas, ni pour E2 ni pour E3</b> (93 à 98 %) : E2 reconnaissait déjà la forme d'un "
   "cerceau recoloré. Ce n'est donc pas la couleur seule qui gênait la détection du cerceau vert en vol (voir §10).",
   "<b>La différence est dans les fausses alarmes</b> : dès que les couleurs changent, E2 en produit jusqu'à 6 sur 30 "
   "(canaux inversés), 21 au total sur les 210 images vides recolorées ; E3 reste à 0 ou 1 (5 au total, toujours la "
   "même image difficile). E2 avait appris « forme + couleurs habituelles de la scène » : avec d'autres couleurs, des "
   "objets ronds ou des encadrements lui ressemblent. E3 est stable quelles que soient les couleurs.",
   "Le centre et le grand axe restent de même précision (9 à 12 px, 4 à 5 %) dans toutes les variantes."])
S.append(Paragraph("À retenir. Sur la validation, E3 est aussi bon qu'E2 avec les couleurs d'origine, et beaucoup plus "
                   "sûr (moins de fausses alarmes) avec d'autres couleurs. C'est la propriété voulue pour un cerceau "
                   "vert ou un éclairage différent. La validation ne contient cependant aucun vrai cerceau vert : seule "
                   "une vidéo réelle annotée mesurerait la détection du vert.", BOX))

# ------------------------------------------------------------------ 10
P("10. Essais en vol avec le cerceau vert (14/10)", H1)
P("Trois vols ont été faits avec E3 (vision_node lancé après le changement de modèle, 18:29, 18:48 et 19:04), dans "
  "le couloir, avec le cerceau vert tenu à la main ou au bout d'une perche. Observations à partir des enregistrements "
  "de l'IHM et du journal de vision_node (logs/vol/).")
fig("fig8_vert.png", 17, "Figure 9 – Vol de 18:29. À 57 et 60 s, l'ellipse (magenta) est posée sur la main et "
    "l'avant-bras qui tiennent le cerceau : le vrai cerceau vert, fin, est visible à côté. À 62 et 64 s, en dessous de "
    "3,7 m, l'ellipse colle exactement au cerceau vert (p = 0,97 puis 1,00).")
fig("fig9_perche.png", 17, "Figure 10 – Vol de 18:51. De 48 à 52 s, l'ellipse englobe la perche blanche et le "
    "cerceau, ou la perche seule : la distance estimée (1,2 m) est fausse. À 53 s, le cerceau vert est bien trouvé.")
tab([["Situation", "Ce qu'on observe", "Cause probable"],
     ["Cerceau vert à moins de 3,7 m", "p entre 0,94 et 1,00 à chaque image, ellipse exacte, mise en axe correcte",
      "La forme est bien apprise : la couleur ne gêne plus"],
     ["Cerceau vert loin (4 à 7 m), tenu à la main", "Ellipse plate sur la main / la manche ; distance estimée 7,5 puis "
      "4,9 m ; delta_x faux (+211 px)", "Tube très fin (1 à 2 px) ; jamais vu de cerceau tenu à la main à "
      "l'entraînement ; l'ellipse est ajustée sur la plus grande zone du masque"],
     ["Cerceau au bout d'une perche", "Grande ellipse englobant perche + cerceau ; distance 0,8 à 1,2 m au lieu de "
      "2 à 3 m ; TRAVERSEE déclenchée à tort", "Perche blanche rectiligne prise pour un morceau d'anneau"],
     ["Cerceau bien plus bas que le drone", "Cerceau trouvé (p = 1) puis perdu par le bas de l'image à 2,1 m",
      "Le drone n'a pas descendu (boucle Z du PC de contrôle) et a continué d'avancer"],
     ["Montées brusques jusqu'au plafond", "delta_z envoyé négatif (« descends ») mais commande Z saturée à +100",
      "Boucle Z du PC de contrôle basée sur le ToF brut (pas le CNN)"]], [4, 6.5, 6.5])
P("Les faux positifs ci-dessus passent la confirmation sur 5 images, car la main ou la perche restent au même endroit "
  "d'une image à l'autre : la confirmation temporelle ne protège pas contre un faux positif stable.")

# ------------------------------------------------------------------ 11
P("11. Bilan E2 / E3", H1)
tab([["Critère", "E2", "E3", "Verdict"],
     ["Perte de validation", "0,7016", "0,6827", "E3"],
     ["Présence (exactitude / précision / rappel)", "95,0 / 98,8 / 94,4 %", "95,8 / 98,9 / 95,6 %", "Égalité (1 image)"],
     ["Centre 2D médian (cage)", "3,9 px", "4,9 px", "Égalité (1 px)"],
     ["Centres à plus de 50 px", "12", "8", "E3"],
     ["Grand axe médian / B/A", "3,9 % / 0,083", "3,0 % / 0,074", "E3"],
     ["Orientation (couloir)", "62°", "28°", "E3"],
     ["AP@0,5 boîte", f(B2["AP50"], 2), f(B3["AP50"], 2), "E3"],
     ["Distance 3D couloir", pc(Q2["couloir"]["dist_rel_med"]), pc(Q3["couloir"]["dist_rel_med"]), "E3"],
     ["Fausses alarmes, validation recolorée", "21 / 210", "5 / 210", "E3"],
     ["Temps de calcul", f"{f(E2['t_cnn'] + E2['t_ell'] + E2['t_pose'], 0)} ms", f"{f(t3, 0)} ms", "Égalité"]],
    [6, 3.6, 3.6, 3.8])
P("<b>E3 est retenu</b> : aussi bon qu'E2 sur le cerceau violet, meilleur sur la taille, l'orientation, les boîtes et "
  "la 3D lointaine, et nettement plus sûr quand les couleurs changent. Il est utilisé par défaut depuis le 14/10 "
  "(vision_node, voir_mqtt, live_detect, localize, HoopDetector). Retour à E2 possible : "
  "python tools/vision_node.py --run logs/E2_segmentation480_0.")

# ------------------------------------------------------------------ 12
P("12. Limites et suite", H1)
tab([["Point", "Piste"],
     ["Aucune image du cerceau vert dans les données", "Filmer le cerceau vert (capture_live) de 1 à 7 m, de face et de "
      "biais ; mesurer le rappel sans annotation (cerceau toujours présent), puis annoter 30 à 50 images"],
     ["Faux positifs sur une main, une manche, une perche", "Ajouter des images de cerceau tenu à la main (et de mains "
      "seules comme images vides) ; essais avec le cerceau sur son pied"],
     ["Ellipse plate de loin (fragment d'anneau)", "Filtre dans ordres.py : rejeter une ellipse très plate (B/A faible) "
      "quand le cerceau est loin"],
     ["Diamètre du cerceau vert", "Le mesurer : configs/hoop.yaml vaut 0,68 m (cerceau violet) ; un autre diamètre fausse "
      "les distances"],
     ["Cerceau perdu par le bas / le haut", "Dans ordres.py : descendre / monter vers la hauteur du cerceau au lieu de "
      "tourner"],
     ["Montées brusques, cerceau perdu par le bas", "PC de contrôle : asservir Z sur delta_z (pas sur le ToF brut), "
      "filtrer le ToF, limiter la commande Z, n'avancer que si |delta_z| < 0,2 m"],
     ["Meilleur modèle choisi sur la perte", "Le choisir sur l'erreur du centre ou la précision"],
     ["Mesures bruitées d'une image à l'autre", "Filtrage temporel (moyenne glissante, Kalman)"]], [6, 11])

# ------------------------------------------------------------------ annexe
P("Annexe – Commandes et fichiers", H1)
S.append(Preformatted(
    "cd ~/Documents/tello && source venv/bin/activate\n\n"
    "# réentraîner E3 puis l'évaluer (galerie logs/E3_segmentation480_couleur_0/predictions.jpg)\n"
    "python -m tellovision.main configs/E3_segmentation480_couleur.yaml train\n"
    "python -m tellovision.main logs/E3_segmentation480_couleur_0 test\n"
    "# courbes E2 / E3\n"
    "tensorboard --logdir logs                      # http://localhost:6006\n"
    "# comparer des modèles sur la même validation\n"
    "python tools/compare_models.py logs/E2_segmentation480_0 logs/E3_segmentation480_couleur_0\n"
    "# en vol (E3 par défaut) ; revenir à E2\n"
    "python tools/vision_node.py\n"
    "python tools/vision_node.py --run logs/E2_segmentation480_0\n"
    "# test sans décollage, flux direct du Tello\n"
    "python tools/live_detect.py\n\n"
    "configs/E3_segmentation480_couleur.yaml   E2 + p_hue_rotate 0,5, p_channel_shuffle 0,3, p_gray 0,2\n"
    "tellovision/data.py           augmentations (hue_rotate, channel_shuffle, grayscale)\n"
    "tellovision/seg.py            masque cible, RingSegNet, perte, masque -> ellipse\n"
    "tellovision/pose.py           ellipse -> cercle 3D (deux solutions, choix)\n"
    "tellovision/detector.py       chaîne complète image -> centre 2D / 3D (modèle E3 par défaut)\n"
    "configs/camera.yaml           calibration de la caméra\n"
    "configs/hoop.yaml             diamètre du cerceau (0,68 m)", CODE))


def deco(c, d):
    c.saveState()
    c.setFont("DV", 7.5)
    c.setFillColor(colors.HexColor("#666666"))
    if d.page > 1:
        c.drawString(2 * cm, 1.2 * cm, "Modèle E3 : segmentation insensible à la couleur et localisation du cerceau")
        c.drawRightString(A4[0] - 2 * cm, 1.2 * cm, str(d.page))
    c.restoreState()


doc = SimpleDocTemplate(PDF, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm,
                        bottomMargin=1.8 * cm, title="Modèle E3 – segmentation insensible à la couleur",
                        author="Projet Tello – partie vision")
doc.build(S, onFirstPage=deco, onLaterPages=deco)
print("ok", PDF)
