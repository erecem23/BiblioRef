# Release notes — BiblioRef 0.9.6 · APP 2.6.4 · Parser 0.5

- Nueva ruta downstream `abnt_author_title_year_end`.
- Parser fuente congelado: `5be695aeb585e02b4eb1b20b96904fb513be87e36950c98487f2572feb8be1d8`.
- Gold externo ABNT 30 referencias congelado: `5773422499c42fbd866b69d457cbaf849310a498f7e2c8ecf6e129960fc3d70c`.
- 0/29.027 referencias históricas activan la ruta nueva: salida histórica preservada.
- Holdout externo: autor 63,33→90%; título fuzzy 0→60%; editorial 5,88→70,59%; tipo 33,33→53,33%.
- Ningún cambio en la segmentación PDF ni en el texto crudo.
- Próximo frente: ABNT con nombres completos + `In:` de revista + tesis/disertaciones.
