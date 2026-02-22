# Titre inline, telechargement source et export

Trois fonctionnalites de la zone de lecture : edition du titre, telechargement de la source originale, et export en JSON ou Markdown.

## Modifier le titre d'une page

Le titre de chaque page est editable directement depuis la zone de lecture, sans ouvrir de formulaire separe.

1. **Cliquez sur le titre** en haut de la zone de lecture. Il se transforme en champ de saisie.

2. Modifiez le texte comme vous le souhaitez.

3. Pour valider :
   - Appuyez sur **Entree**
   - Ou **cliquez n'importe ou en dehors** du champ : la modification est sauvegardee automatiquement

4. Pour annuler, appuyez sur **Echap** : le titre revient a sa valeur precedente.

> **Note** : Le titre modifie est immediatement mis a jour dans l'arbre de navigation a gauche.

## Telecharger la source originale

Un bouton **"Source"** apparait sous le titre de chaque page. Il permet de recuperer le fichier original ayant servi a creer la page.

Le comportement depend du type de source :

| Type de page | Ce qui est telecharge |
|---|---|
| **Audio** (avec fichier) | Le fichier audio original (.mp3, .wav, etc.) |
| **Audio** (import JSON, sans fichier audio) | Le JSON brut de la transcription |
| **Document** (PDF, DOCX, etc.) | Le fichier original uploade |
| **Page web** | Le HTML original capture par l'extension |

> **Note** : Pour les pages importees avant l'ajout de cette fonctionnalite, le fichier source n'est pas disponible. Dans ce cas, pour les transcriptions audio, le JSON brut est propose a la place.

## Exporter une page

Un bouton **"Exporter"** apparait a cote du bouton Source. Il ouvre un menu avec les options d'export disponibles.

### Pages audio (transcriptions)

- **Export JSON** : telecharge un fichier `.json` contenant les segments de transcription avec locuteurs, timestamps et texte. Ce fichier est **re-importable** dans Hypostasia (les modifications de locuteurs et de texte sont conservees).

- **Export Markdown** : telecharge un fichier `.md` avec le format :
  ```
  # Titre de la transcription

  **[Locuteur 00:01:23]**
  Texte du segment...
  ```

### Pages web et documents

- **Export Markdown** : telecharge un fichier `.md` contenant le titre et le texte lisible de la page.

> **Astuce** : L'export JSON d'une transcription audio est le meilleur moyen de sauvegarder votre travail d'edition (renommages de locuteurs, corrections de texte). Le fichier peut etre reimporte pour retrouver exactement le meme etat.
