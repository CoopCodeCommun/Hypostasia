# Le voisinage de Docling — ce que `nice` achète, et ce qu'il n'achète pas

**18 août 2026.** Machine à 8 cœurs, 22 Go, aucune limite Docker.
Juge local à **6 threads**. Docling = `make test-docling`, 8 conversions
réelles.

---

## Les quatre mesures

| condition | Docling (8 conversions) | juge local (s/paire) |
|---|---|---|
| **chacun seul** | **130,6 s** | **23,8 s** |
| ensemble, juge local sous **`nice -n 19`** | **124,7 s** | 27,7 s **(+16 %)** |
| ensemble, juge local **sans nice** | **139,9 s** | 26,6 s (+12 %) |

## Ce que ça dit

**`nice` achète environ 11 % du temps mural de Docling** — 139,9 s contre
124,7 s selon que le juge local est déprioritisé ou non. C'est réel, et c'est
modeste.

**Docling ne perd que 7 % sans aucune protection** (130,6 → 139,9 s). L'idée que
« Docling mourrait de faim » à côté du juge local est donc **exagérée pour ce
qui concerne `nice`**. Les protections qui portent vraiment sont ailleurs :

1. **la file dédiée à concurrence 1**, qui empêche deux inférences simultanées —
   ce serait douze threads sur huit cœurs, et là, oui ;
2. **le plafond de threads** (6, « tout moins deux »), le seul levier sur la
   bande passante mémoire, que `nice` ne pondère pas.

**Le juge local paie le voisinage : +16 % sous `nice`, +12 % sans.** Ce n'est
pas une erreur de lecture — sous `nice` il cède davantage, ce qui est
exactement son office.

## La réserve, et elle est de taille

**Une seule passe par condition.** L'inversion « chacun seul 130,6 s » contre
« ensemble sous nice 124,7 s » — Docling plus *rapide* accompagné que seul —
montre que le bruit est de l'ordre de **±5 %**. Le « +7 % » de Docling sans nice
est donc **à peine au-dessus du bruit**.

Ce qu'il faudrait pour trancher : trois passes par condition, et un ordre
d'exécution alterné pour absorber l'effet de cache.

## Ce que ça change pour le réglage

Rien, pour l'instant. `SHIELDSTRAL_THREADS=6` reste le défaut, et `nice -n 19`
reste en place — il ne coûte rien et il va dans le bon sens. Mais **on sait
maintenant que ce n'est pas lui qui protège Docling** : si un jour le voisinage
devient gênant, c'est le nombre de threads qu'il faudra baisser, pas la
priorité qu'il faudra creuser.

## Rejouer

```bash
# chacun seul
make test-docling
docker exec -w /app hypostasia_web python \
    benchmarks/juge_local/mesurer_les_threads.py --threads 6 --paires 5

# ensemble : lancer Docling en boucle dans un terminal…
make test-docling; make test-docling

# …et pendant ce temps, dans un autre :
docker exec -w /app hypostasia_web nice -n 19 python \
    benchmarks/juge_local/mesurer_les_threads.py --threads 6 --paires 5
```

Le juge local ne touche jamais la base : cette mesure se rejoue à l'identique
avant comme après une reconstruction.
