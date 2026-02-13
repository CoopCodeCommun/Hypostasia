"""
Service de conversion de fichiers en HTML + texte pour import dans Hypostasia.
/ File conversion service to HTML + text for import into Hypostasia.

Supporte : PDF, DOCX, PPTX, XLSX, MD, TXT.
Ne stocke pas le fichier source — seuls le HTML et le texte convertis sont conserves.
/ Supports: PDF, DOCX, PPTX, XLSX, MD, TXT.
Does not store the source file — only the converted HTML and text are kept.
"""

import logging
import os
import tempfile

logger = logging.getLogger(__name__)


def convertir_fichier_en_html(fichier_uploade, nom_fichier):
    """
    Convertit un fichier uploade en (html_readability, text_readability, titre).
    / Converts an uploaded file to (html_readability, text_readability, title).

    Args:
        fichier_uploade: Django UploadedFile (ou tout objet avec .read())
        nom_fichier: Nom original du fichier (str)

    Returns:
        tuple (html_readability, text_readability, titre)

    Raises:
        ValueError: Si l'extension n'est pas supportee
    """
    from front.utils import extraire_texte_depuis_html

    extension = os.path.splitext(nom_fichier)[1].lower()
    nom_sans_extension = os.path.splitext(nom_fichier)[0]

    # Dispatch selon l'extension du fichier
    # / Dispatch based on file extension
    if extension == ".docx":
        contenu_html = _convertir_docx(fichier_uploade)
    elif extension == ".pdf":
        contenu_html = _convertir_via_markitdown(fichier_uploade, nom_fichier)
    elif extension in (".pptx", ".xlsx"):
        contenu_html = _convertir_via_markitdown(fichier_uploade, nom_fichier)
    elif extension == ".md":
        contenu_html = _convertir_markdown(fichier_uploade)
    elif extension == ".txt":
        contenu_html = _convertir_texte_brut(fichier_uploade)
    else:
        raise ValueError(f"Extension non supportee : {extension}")

    # Deriver le texte lisible depuis le HTML converti
    # / Derive readable text from converted HTML
    texte_readability = extraire_texte_depuis_html(contenu_html)

    # Titre : extrait du premier heading HTML ou du nom de fichier
    # / Title: extracted from first HTML heading or from filename
    titre = _extraire_titre_depuis_html(contenu_html) or nom_sans_extension

    return contenu_html, texte_readability, titre


def _convertir_docx(fichier_uploade):
    """
    Convertit un fichier DOCX en HTML via mammoth.
    / Converts a DOCX file to HTML via mammoth.
    """
    import mammoth

    resultat_conversion = mammoth.convert_to_html(fichier_uploade)
    if resultat_conversion.messages:
        for message in resultat_conversion.messages:
            logger.warning("mammoth: %s", message)
    return resultat_conversion.value


def _convertir_via_markitdown(fichier_uploade, nom_fichier):
    """
    Convertit un fichier (PDF, PPTX, XLSX) en HTML via MarkItDown → Markdown → mistune.
    Ecrit le fichier dans un tempfile car MarkItDown a besoin d'un chemin.
    / Converts a file (PDF, PPTX, XLSX) to HTML via MarkItDown → Markdown → mistune.
    Writes the file to a tempfile because MarkItDown needs a file path.
    """
    from markitdown import MarkItDown
    import mistune

    extension = os.path.splitext(nom_fichier)[1].lower()

    # Ecrire le contenu dans un fichier temporaire avec la bonne extension
    # / Write content to a temp file with the correct extension
    with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as fichier_temp:
        for morceau in fichier_uploade.chunks():
            fichier_temp.write(morceau)
        chemin_temporaire = fichier_temp.name

    try:
        convertisseur = MarkItDown()
        resultat_markdown = convertisseur.convert(chemin_temporaire)
        contenu_markdown = resultat_markdown.text_content

        # Convertir le Markdown en HTML via mistune
        # / Convert Markdown to HTML via mistune
        contenu_html = mistune.html(contenu_markdown)
        return contenu_html
    finally:
        # Nettoyage du fichier temporaire
        # / Clean up temporary file
        os.unlink(chemin_temporaire)


def _convertir_markdown(fichier_uploade):
    """
    Convertit un fichier Markdown en HTML via mistune.
    / Converts a Markdown file to HTML via mistune.
    """
    import mistune

    contenu_brut = fichier_uploade.read()
    if isinstance(contenu_brut, bytes):
        contenu_brut = contenu_brut.decode("utf-8")
    return mistune.html(contenu_brut)


def _convertir_texte_brut(fichier_uploade):
    """
    Convertit un fichier TXT en HTML (chaque ligne devient un <p>).
    / Converts a TXT file to HTML (each line becomes a <p>).
    """
    contenu_brut = fichier_uploade.read()
    if isinstance(contenu_brut, bytes):
        contenu_brut = contenu_brut.decode("utf-8")

    lignes_html = []
    for ligne in contenu_brut.splitlines():
        ligne_nettoyee = ligne.strip()
        if ligne_nettoyee:
            lignes_html.append(f"<p>{ligne_nettoyee}</p>")
    return "\n".join(lignes_html)


def _extraire_titre_depuis_html(contenu_html):
    """
    Extrait le titre depuis le premier heading (h1-h3) du HTML.
    Retourne None si aucun heading trouve.
    / Extracts title from the first heading (h1-h3) in HTML.
    Returns None if no heading found.
    """
    import re

    match = re.search(r"<h[1-3][^>]*>(.*?)</h[1-3]>", contenu_html, re.IGNORECASE | re.DOTALL)
    if match:
        # Retirer les balises HTML internes du titre
        # / Strip inner HTML tags from title
        titre_brut = re.sub(r"<[^>]+>", "", match.group(1)).strip()
        if titre_brut:
            return titre_brut[:500]
    return None
