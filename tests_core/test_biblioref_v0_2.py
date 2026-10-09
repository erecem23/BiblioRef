from biblioref_v0_2 import (
    diagnose_style, is_reference_start, segment_lines, process_pdf,
    reference_fingerprint, _annotate_duplicates, _select_scope,
)
from pathlib import Path
import json, csv

CASES = {
    'fiorucci_author_year': {
        'lines': [
            'Aarnikoivu, M.; Nokkala, T.; Siekkinen, T.; Kuoppala, K. y Pekkola, E. (2019). Working outside academia?',
            'European Journal of Higher Education, Vol. 9/2, pp. 172-189.',
            'Abbattista, M. L.; Barletta, A. y Lenci, L. (2016). La historia va al tribunal en La Plata.',
            'Transiciones, memorias e identidades en Europa y América Latina. Madrid: Iberoamericana.',
            'Abbattista, M. L. (2019). Justicialismo y cultura en la Guerra Fría.',
            'Acosta, F.; Fernández, S.; Ríos, L. (2015). Universidades fundacionales y universidades de creación reciente.',
            'Albornoz, M., Fernández Polcuch, E. & Alfaraz, C. (2002). Hacia una nueva estimación de la fuga de cerebros.',
            'Albornoz, M. (2004). Política científica y tecnológica en Argentina.',
            'Albornoz, M. (2007). Los problemas de la ciencia y el poder.',
            'Albornoz, M. y Gordon, A. (2011). La política de ciencia y tecnología en Argentina desde la recuperación de la democracia.'
        ],
        'gold_starts': 8,
        'style': 'author_year_comma'
    },
    'iermano_author_initial': {
        'lines': [
            'Aizen M, Garibaldi L & M Dondo (2009) Expansión de la soja y diversidad de la agricultura argentina.',
            'Revista Ecología Austral 19:45-54.',
            'Albanesi R (2007). La modernización en el devenir de la producción familiar capitalizada.',
            'Alessandria E, Leguía H, Pietrarelli L, Sánchez J, Luque S, Arbono M, Zamar JI & D Rubin (2001). La agrobiodiversidad en sistemas extensivos.',
            'Alluvione F, Moretti B, Sacco D & C Grignani (2011). EUE of cropping systems for a sustainable agriculture.',
            'Altieri M & C Nicholls (1999). Biodiversity, Ecosystem Function, and Insect Management In Agricultural Systems.',
            'Altieri M & C Nicholls (2000). Agroecología. Teoría y práctica para una agricultura sustentable.',
            'Altieri M & C Nicholls (2006). Optimizando el manejo agroecológico de plagas a través de la salud del suelo.',
            'Altieri M & C Nicholls (2007). Biodiversidad y manejo de plagas en agroecosistemas.',
            'Altieri M & VM Toledo (2011). La revolución agroecológica en Latinoamérica.',
            'Altieri M (1994). Biodiversity and pest management in agroecosystems.',
            'Balsa J & N López Castro (2011). La agricultura familiar moderna.',
            'Balsa J (2002). Transformaciones en la estructura agraria pampeana y en las formas de producción de la agricultura, 1937-1969.',
            'Balsa, J (2008) Cambios y continuidades en la agricultura pampeana entre 1937 y 2002.'
        ],
        'gold_starts': 13,
        'style': 'author_initial'
    },
    'stoffel_numeric': {
        'lines': [
            '1. Aguilera, J., San Martin, R. «Steam Hydrolysis of Pine sawdust.» Biomass 8,',
            '1985: 301-313.',
            '2. Akerholm, M., Salmén, L. «Interactions between wood polymers studied by dynamic FT-IR spectroscopy.» Polymer 42, 2001: 963-969.',
            '3. Alén, R. «Chapter 3A - Pulp Mills and Wood-Based Biorefineries.»',
            'En Industrial Biorefineries & White Biotechnology, 91-126. Elsevier, 2015.',
            '4. Alén, R. «Structure and chemical composition of wood.» En Forest Products Chemistry, 2000.',
            '5. Alonso-Sande, M., Teijeiro-Osorio, D., Remuñán-López, C., Alonso, M.J. «Glucomannan...» 2009.',
            '6. Alvarez Vasco, C., Guo, M., Zhang, X. «Dilute Acid Pretreatment...» 2015.',
            '7. Anglés Neus, M., Reguant, J., Garcia Balls, R., Salvadó, J. «Characteristics of lignin...» 2003.',
            '8. Area, M.C., Vallejos, M.E. «La biorrefinería Forestal.» 2012.',
            '9. ArgenBio, Consejo Argentino para la Información y el Desarrollo de la Biotecnología. 2011.',
            'http://www.argenbio.org/index.php?action=notas&note=5683',
            '10. Arshadi, M., Backlund, I., Geladi, P., Bergsten, U. «Comparison...» 2013.'
        ],
        'gold_starts': 10,
        'style': 'numeric'
    },
    'sanz_bracket_key': {
        'lines': [
            '[Ang97] Edward Angel',
            '“Interactive Computer Graphic. A top – down approach with OpenGL”',
            'Adisson Wesley Logman. 1997.',
            'Es un libro que presenta los aspectos principales de computación gráfica.',
            '[Bax94] Gregory A. Baxes',
            '"Digital Image Processing. Principles and Applications"',
            'John Wiley & Sons Inc. 1994.',
            'Se trata de un libro que presenta en forma sencilla los conceptos básicos.',
            '[Bis95] Christopher M. Bishop',
            '"Neural Networks for Pattern Recognition"',
            'Clarendon Press Oxford. 1995.',
            'Este libro provee un primer tratamiento comprensivo sobre redes neuronales.',
            '[Bra94] Ronald N. Bracewell',
            '“Two – Dimensional Imaging”',
            'Prentice Hall. 1994.',
            'En este libro se desarrollan conceptos sobre las imágenes vistas como señales.',
            '[Bru2000] Lorenzo Bruzzone',
            '“An approach to feature selection and classification of remote sensing images based on the Bayes rule for minimum cost”.',
            'IEEE Transactions on Geoscience and Remote Sensing. Vol. 38, Nro.1. Enero 2000.',
            'Se trata de un trabajo en donde se describe un método de clasificación basado en la regla de Bayes.'
        ],
        'gold_starts': 5,
        'style': 'bracket_key',
        'gold_annotations': 5
    },
    'benavidez_numeric_ocr': {
        'lines': [
            '1) BELTRAN JUAN RAMON; "Historia del Protomedicato",',
            'en España - Ed. Ateneo, 1937.-',
            '2) GARCIA DEL REAL - "Medicina entre los Aztecas".-',
            '3) FELIX GARZON MACEDA: "Historia de la Facultad de Medicina de Córdoba", tomo 1.-',
            '4) Ley 13.031.-',
            '5) Proyecto de Código penal de 1906.-',
            '6) Exposición de motivos del proyecto de Código penal por la República Argentina, 1906, pág. LXII.-',
            '7) Tratado de Derecho penal de Sebastián SOLER, tomo IV, pág. 620.-',
            '8) GABRIEL DEL MAZZO; "Reforma Universitaria".-',
            '9) Tratado de Derecho Penal; ob. op. cit., tomo IV, pág.624.-',
            '10) Parte de la ley 12.912.-'
        ],
        'gold_starts': 10,
        'style': 'numeric'
    }
}

def challenge_rows():
    rows=[]
    for name,c in CASES.items():
        prof=diagnose_style(c['lines'])
        starts=sum(is_reference_start(x,prof) for x in c['lines'])
        segs=segment_lines(c['lines'],prof)
        anns=sum(bool(s.get('annotation_text')) for s in segs)
        rows.append({
            'case': name, 'expected_style': c['style'], 'detected_style': prof.style,
            'gold_starts': c['gold_starts'], 'detected_starts': starts,
            'segments': len(segs), 'annotations_detected': anns,
            'annotation_gold': c.get('gold_annotations',''),
            'pass_style': prof.style==c['style'],
            'pass_starts': starts==c['gold_starts'],
        })
    return rows


def test_development_challenge():
    rows = challenge_rows()
    assert all(r['pass_style'] for r in rows), rows
    assert all(r['pass_starts'] for r in rows), rows
    sanz = next(r for r in rows if r['case'] == 'sanz_bracket_key')
    assert sanz['annotations_detected'] == sanz['annotation_gold']


def test_fingerprint_ignores_accents_spacing_and_punctuation():
    a = 'Pichón-Rivière, E. (1977). Psicología social.'
    b = 'Pichon Riviere E 1977 Psicologia social'
    assert reference_fingerprint(a) == reference_fingerprint(b)


def test_duplicate_reporting_and_scopes():
    records = [
        {'zone_id': 1, 'ref_in_zone': 1, 'zone_start_page': 10,
         'reference_text': 'Autor, A. (2020). Título.'},
        {'zone_id': 2, 'ref_in_zone': 1, 'zone_start_page': 20,
         'reference_text': 'Autor A 2020 Titulo'},
        {'zone_id': 2, 'ref_in_zone': 2, 'zone_start_page': 20,
         'reference_text': 'Otra, B. (2021). Obra.'},
    ]
    annotated, groups = _annotate_duplicates(records)
    assert len(groups) == 1
    assert groups[0]['occurrence_count'] == 2
    assert annotated[0]['is_repeated_across_zones'] is True
    assert len(_select_scope(annotated, 'all_reference_sections')) == 3
    assert len(_select_scope(annotated, 'final_reference_section')) == 2
    unique = _select_scope(annotated, 'unique_references')
    assert len(unique) == 2
    assert unique[0]['duplicate_occurrence_count'] == 2


if __name__ == '__main__':
    rows = challenge_rows()
    outdir = Path(__file__).resolve().parent
    with open(outdir / 'biblioref_v0_2_challenge.csv','w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print('CHALLENGE')
    for r in rows: print(r)

    # Optional full-PDF smoke test when a local path is supplied.
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--pdf')
    args = ap.parse_args()
    if args.pdf:
        for scope in ('all_reference_sections', 'final_reference_section', 'unique_references'):
            full = process_pdf(args.pdf, scope=scope)
            (outdir / f'biblioref_v0_2_{scope}.json').write_text(
                json.dumps(full,ensure_ascii=False,indent=2), encoding='utf-8'
            )
            print(scope, {k:v for k,v in full.items() if k not in ('records','zones','duplicate_groups')})
