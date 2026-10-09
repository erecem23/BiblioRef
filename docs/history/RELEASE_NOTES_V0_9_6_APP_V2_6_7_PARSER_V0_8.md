# Release notes — BiblioRef 0.9.6 · APP 2.6.7 · Parser 0.8

- Parser downstream v0.8, schema 8.
- Extractor 0.9.6 sin cambios.
- Mejor limpieza de títulos de tesis/disertaciones y fronteras `?`/`!` + `In:`.
- Mejoras conservadoras de autores, publisher y candidatos a revista.
- Dos holdouts externos congelados: 30 referencias generales y 20 de estrés.
- Holdout general: 0 mejoras / 0 regresiones vs v0.7.
- Stress holdout: título fuzzy>=.90 35% → 55%, 4 mejoras / 0 regresiones; año y DOI 100%.
- Limitación: revista sigue sin normalizar correctamente en el stress holdout (0/8 fuzzy>=.90 pese a 87,5% de cobertura).
- Parser SHA-256: `b10079270b5df316ebbab4ad667df774280ab09f899f5b472f1e09f372bd885b`.
