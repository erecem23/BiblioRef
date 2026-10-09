# Parser v0.11 — candidate

BiblioRef extractor/app se mantienen sobre la base v0.9.8 + APP 2.6.9. El único cambio funcional de esta rama es el parser downstream público, que pasa de v0.10/schema 10 a **v0.11/schema 11**.

v0.11 agrega el régimen `legacy_year_final` observado en una tesis de Sociología de la Universidad de Belgrano y mantiene v0.10 como ruta congelada para APA/ABNT y demás entradas que no cumplen la nueva firma.

Estado: **development candidate**. Palma es corpus de desarrollo; el siguiente paso debe ser un holdout externo de bibliografías con año final antes de promover el parser.
