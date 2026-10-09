# Release notes — BiblioRef 0.9.6 · APP 2.6.5 · Parser 0.6

- ABNT ampliado: nombres desarrollados, variantes de iniciales, `In:` contextual, Tese/Dissertação y revistas menos rígidas.
- Parser congelado antes del holdout: `c09e87c6f76552d5b3e0f29f846e896224a81c353f2b60eeb4c0c34fb479c942`.
- Gold externo de 30 referencias (UFMG/UnB/UFRGS): `23d575357fd38c0e54e2a497610d1339550fba31d70f2198e09d146d35f3bbb5`.
- 0/29.027 referencias históricas activan la ruta ampliada: semántica histórica preservada.
- Holdout externo: título fuzzy 3,33→73,33%; tipo 3,33→70%; editorial 3,57→50%; cobertura revista 0→100%.
- Regresiones transparentes: autor 83,33→73,33% (3 pares) y una regresión de año compensada por una mejora.
- No hubo cambios post-holdout en `v06.py`; el extractor PDF permanece congelado.
- Próximo frente: semántica de primer autor, URLs en año, limpieza de revista y variantes `(in)`/autores sin coma.
