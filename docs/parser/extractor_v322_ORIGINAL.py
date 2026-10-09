
# ==============================================================================
# EXTRACTOR BIBLIOMETRICO V3.2.2 — Para Google Colab
# Reemplazo completo de V3.2 con clasificación fina y multireferencias
# ==============================================================================

# ════════════ CELDA 1 — Instalacion ═══════════════════════════════════════
# !pip install PyMuPDF tqdm -q

# ════════════ CELDA 2 — Imports y configuracion ════════════════════════════

import fitz
import re, unicodedata, pandas as pd, os, logging, shutil
from pathlib import Path
from collections import defaultdict
from tqdm.auto import tqdm

logging.basicConfig(filename='auditoria_v32.log', level=logging.WARNING,
                    format='%(asctime)s - %(levelname)s - %(message)s')


PUBLISHER_RE = re.compile(
    r'\b('
    r'press|university press|academic press|oxford university press|cambridge university press|'
    r'routledge|springer|sage|wiley|elsevier|guilford press|manual moderno|'
    r'az editora|editorial teseo|american psychological association|apa books|'
    r'paid[oó]s|paidos|pearson'
    r')\b',
    flags=re.IGNORECASE
)

REPOSITORY_RE = re.compile(
    r'\b('
    r'archivo digital|repositorio|repository|sedici|rdu|memoria acad[eé]mica|'
    r'facultad de|universidad nacional|universidad de|institute of education sciences|'
    r'u\.s\. department of education|national center for|centre for'
    r')\b',
    flags=re.IGNORECASE
)

ARTICLE_CUE_RE = re.compile(
    r'(\b\d+\(\d+\)\b|\b\d{1,4}\s*[-–]\s*\d{1,4}\b|(?:https?://(?:dx\.)?doi\.org/|doi\s*:?\s*)10\.\d{4,9}/)',
    flags=re.IGNORECASE
)

REVISTA_CUE_RE_GLOBAL = re.compile(
    r'\b('
    r'journal|review|revista|anales|annals|proceedings|'
    r'psychology|psychiatry|oncology|medicine|medical|'
    r'behaviour|behavior|research|therapy|physiology|mapping|'
    r'neuroimage|cortex|brain|psychotherapy|'
    r'computers in human behavior|human brain mapping|'
    r'frontiers in|psycho-oncology|bmc research notes|'
    r'clinical|cognitive|salud|educación|educacion|clin'
    r')\b',
    flags=re.IGNORECASE
)

def candidato_no_es_revista(cand: str) -> bool:
    if not isinstance(cand, str):
        return True
    c = cand.strip()
    if not c:
        return True
    if PUBLISHER_RE.search(c):
        return True
    if REPOSITORY_RE.search(c):
        return True
    if len(c.split()) > 10:
        return True
    return False

AUTORES_VIP = {
    r'\bFreud\b':                             'Freud, S.',
    r'\bLacan\b':                             'Lacan, J.',
    r'\bKlappenbach\b':                       'Klappenbach, H.',
    r'\bPiñeda\b|\bPineda\b':                 'Piñeda, M.',
    r'\bV[iy]got[s]?k[iy]\b':                 'Vygotsky, L. S.',
    r'\bOMS\b|Organización Mundial':          'OMS',
    r'\bOPS\b|Organización Panamer':          'OPS',
    r'\bUNESCO\b':                            'UNESCO',
    r'\bUNICEF\b':                            'UNICEF',
    r'\bAPA\b|American Psychological':        'American Psychological Association',
}

EDITORIALES_NORM = {
    r'Paidos|Paídos|Paidós Ibérica':          'Paidós',
    r'Siglo Veintiuno|Siglo XXI Editores':    'Siglo XXI',
    r'Fondo de [Cc]ultura [Ee]con':           'Fondo de Cultura Económica',
    r'Lawrence Erlbaum|Erlbaum':              'Erlbaum',
    r'McGraw.Hill|Mc Graw Hill|McGraw Hill':  'McGraw-Hill',
    r'Sage Publications|SAGE':                'Sage',
    r'John Wiley|Wiley & Sons':               'Wiley',
    r'The Guilford Press':                    'Guilford Press',
    r'Alianza Editorial':                     'Alianza',
    r'Ediciones Morata':                      'Morata',
    r'Nueva [Vv]isión':                       'Nueva Visión',
}

print('✅ Configuración cargada.')


# ════════════ CELDA 3 — Motor de extracción V3.2 ═══════════════════════════

class ExtractorV32:
    """
    V3.2:
    - Prioriza headings explícitos de referencias en la parte final del PDF.
    - Usa fallback por densidad SOLO si no hay heading.
    - Excluye PDFs con texto ilegible / OCR muy defectuoso.
    - Mantiene segmentación por sangría APA.
    """

    RE_HEADER = re.compile(
        r'^\s*(?:(?:parte|sección|seccion|capítulo|capitulo)\s+[IVXLCDM\d]+\.?\s*|[IVXLCDM\d]+\.?\s*)?'
        r'(lista de referencias|listado de referencias|reference list|references list|'
        r'referencias generales|bibliografía general|bibliografia general|'
        r'referencias bibliográficas|referencias bibliograficas|referencias citadas|'
        r'referencias|bibliografía|bibliografia|obras citadas|fuentes consultadas|'
        r'literatura citada|trabajos citados|referencias y bibliografía|referencias y bibliografia)'
        r'[^a-zA-Z]*$',
        re.IGNORECASE
    )
    RE_FIN = re.compile(
        r'^\s*(anexos?|apéndices?|apendices?|apéndice\s+[A-Z\d]|apendice\s+[A-Z\d]|anexo\s+[A-Z\d])\s*',
        re.IGNORECASE
    )
    RE_APA = re.compile(
        r'^(?:[A-ZÁÉÍÓÚÑ\[]|de |van |von |da |di |del ).{2,150}'
        r'\(\s*(?:(?:19|20)\d{2}[a-z]?(?:/[12]\d{3}[a-z]?)?|s\.f\.)\s*\)'
    )
    RE_NUMERICO = re.compile(r'^\s*\[?\d{1,3}\]?[.\-]?\s+(?!http|doi)')
    RE_INSTITUCIONAL = re.compile(
        r'^(Organización|Organizacion|Ministerio|Universidad|Facultad|Instituto|Centro|'
        r'Asociación|Asociacion|OMS|OPS|ONU|Cooperativa|Fundación|Fundacion|Dirección|Direccion|'
        r'Secretaría|Secretaria|Comité|Comite|Academia|Sociedad|Gobierno|Colegio|Banco|Agencia|'
        r'UNESCO|UNICEF|WHO|APA|DSM|Ley N|Decreto|Resolución|Resolucion|Código|Codigo)\b',
        re.IGNORECASE
    )
    RE_AUTOR = re.compile(
        r'^(?:[A-ZÁÉÍÓÚÑ][a-z\-áéíóúñ]+\s*,?\s+[A-ZÁÉÍÓÚÑ])'
    )
    RE_ANIO = re.compile(r'\b(?:18|19|20)\d{2}\b')
    RE_VIETA = re.compile(r'^[\-\u2022\u25cf\u25aa\u2013\u2014·\uf0b7\uf0a7\u25b6]+\s*')
    RE_ANIO_INICIAL = re.compile(
        r'^(?:[A-Z]\.\s*){1,4}\(\s*(?:(?:19|20)\d{2}[a-z]?(?:/[12]\d{3}[a-z]?)?|s\.f\.)\s*\)'
    )
    RE_AUTORES_SOLOS = re.compile(
        r'^(?:[A-ZÁÉÍÓÚÑ][a-záéíóúñ\-]+,\s*(?:[A-Z]\.\s*){1,3}(?:,\s*|\s+y\s+|\s+and\s+|\s+&\s+)){2,}.+$',
        re.IGNORECASE
    )

    def __init__(self, out_refs_dir):
        self.out_refs_dir = Path(out_refs_dir)
        self.out_refs_dir.mkdir(parents=True, exist_ok=True)
        self.exclusiones = []

    def _extraer(self, pdf_path):
        try:
            doc = fitz.open(pdf_path)
            toc_start = None
            for level, title, page in doc.get_toc():
                if self.RE_HEADER.match(title.strip()):
                    toc_start = max(0, page - 1)

            pages_data = []
            ocurrencias = defaultdict(list)

            for pnum, page in enumerate(doc):
                ph = page.rect.height
                lineas = []
                text_dict = page.get_text('dict', flags=fitz.TEXT_PRESERVE_WHITESPACE)
                for block in text_dict.get('blocks', []):
                    if block.get('type') != 0:
                        continue
                    for line in block.get('lines', []):
                        spans = line.get('spans', [])
                        if not spans:
                            continue
                        txt = ''.join(s['text'] for s in spans).strip()
                        if not txt:
                            continue
                        x0 = spans[0]['bbox'][0]
                        yc = (line['bbox'][1] + line['bbox'][3]) / 2
                        yr = yc / ph
                        size = max(s['size'] for s in spans)
                        lineas.append({'text': txt, 'x0': x0, 'y_ratio': yr,
                                       'size': size, 'page': pnum})
                        if yr <= 0.12 or yr >= 0.88:
                            if not self.RE_HEADER.match(txt):
                                norm = re.sub(r'\d+', '', re.sub(r'\s+', ' ', txt).lower()).strip()
                                if 3 < len(norm) <= 180:
                                    ocurrencias[norm].append(pnum)
                pages_data.append(lineas)

            doc.close()
            removable = {k for k, v in ocurrencias.items() if len(set(v)) >= 3}

            clean = []
            for plines in pages_data:
                kept = []
                for ln in plines:
                    if ln['y_ratio'] <= 0.12 or ln['y_ratio'] >= 0.88:
                        norm = re.sub(r'\d+', '', re.sub(r'\s+', ' ', ln['text']).lower()).strip()
                        if norm in removable:
                            continue
                        if ln['size'] < 8 and not self.RE_HEADER.match(ln['text']):
                            continue
                    kept.append(ln)
                clean.append(kept)

            return clean, toc_start
        except Exception as e:
            logging.error(f'Error en {pdf_path.name}: {e}')
            return [], None

    def _texto_muestra(self, clean_pages, max_paginas=10, max_lineas=120):
        partes = []
        for page in clean_pages[:max_paginas]:
            for ln in page[:max_lineas]:
                partes.append(ln['text'])
        return ' '.join(partes)

    def _pdf_legible(self, clean_pages):
        sample = self._texto_muestra(clean_pages).strip()
        if len(sample) < 200:
            return True, ''
        sample_ns = re.sub(r'\s+', '', sample)
        if not sample_ns:
            return False, 'sin_texto_extraible'

        alpha = sum(ch.isalpha() for ch in sample_ns)
        alnum = sum(ch.isalnum() for ch in sample_ns)
        weird = sum(ch in '#$%&/\\@~^*_+=<>|¬¦§' for ch in sample_ns)
        alpha_ratio = alpha / max(len(sample_ns), 1)
        alnum_ratio = alnum / max(len(sample_ns), 1)
        weird_ratio = weird / max(len(sample_ns), 1)

        tokens = re.findall(r'[A-Za-zÁÉÍÓÚÑáéíóúñ]{3,}', sample)
        vocalizados = sum(bool(re.search(r'[aeiouáéíóú]', tok, re.I)) for tok in tokens)
        vocal_ratio = vocalizados / max(len(tokens), 1) if tokens else 0

        if re.search(r"[&%#\*\+\-/]{3,}", sample) and alpha_ratio < 0.40:
            return False, f'texto_corrupto_patron_copia_alpha={alpha_ratio:.2f}'
        if alnum_ratio < 0.45 and weird_ratio > 0.10:
            return False, f'texto_corrupto_alnum={alnum_ratio:.2f}_weird={weird_ratio:.2f}'
        if len(tokens) >= 20 and vocal_ratio < 0.45:
            return False, f'texto_posible_imagen_ocr_defectuoso_vocal_ratio={vocal_ratio:.2f}'

        return True, ''

    def _aislar(self, clean_pages, toc_start):
        total = len(clean_pages)
        if total == 0:
            return []

        zona_heading = max(0, int(total * 0.45))
        heading_candidates = []

        def linea_es_toc(txt):
            return bool(re.search(r'\.{3,}\s*\d+$|\s{2,}\d+$', txt))

        def score_pagina(lineas):
            score = 0
            for ln in lineas[:160]:
                txt = ln['text'].strip()
                if not txt or linea_es_toc(txt):
                    continue
                if self.RE_APA.search(txt):
                    score += 3
                elif self.RE_INSTITUCIONAL.search(txt):
                    score += 2
                elif self.RE_AUTOR.search(txt) and self.RE_ANIO.search(txt):
                    score += 2
                elif self.RE_ANIO.search(txt):
                    score += 1
                if re.search(r'10\.\d{4,9}/|https?://|www\.', txt, re.I):
                    score += 2
                if re.search(r'\b\d+\s*\(\d+\)\b|\b\d{1,4}\s*[-–]\s*\d{1,4}\b', txt):
                    score += 1
            return score

        for i in range(zona_heading, total):
            upper = clean_pages[i][:18]
            for j, ln in enumerate(upper):
                txt = ln['text'].strip()
                if not txt or linea_es_toc(txt):
                    continue
                if self.RE_HEADER.match(txt):
                    page_score = score_pagina(clean_pages[i])
                    if page_score >= 4:
                        heading_candidates.append((i, j))
                        break

        if toc_start is not None and zona_heading <= toc_start < total:
            upper = clean_pages[toc_start][:18]
            for j, ln in enumerate(upper):
                txt = ln['text'].strip()
                if txt and self.RE_HEADER.match(txt) and not linea_es_toc(txt):
                    heading_candidates.append((toc_start, j))
                    break

        if heading_candidates:
            heading_candidates = sorted(set(heading_candidates), key=lambda x: (x[0], x[1]))
            sp, sl = heading_candidates[0]
        else:
            fallback_start = max(0, int(total * 0.55))
            scored_pages = [(i, score_pagina(clean_pages[i])) for i in range(fallback_start, total)]
            valid_pages = [(i, s) for i, s in scored_pages if s >= 7]

            if valid_pages:
                sp, sl = sorted(valid_pages, key=lambda x: x[0])[0][0], 0
            else:
                best_i, best_score = max(scored_pages, key=lambda x: x[1]) if scored_pages else (None, None)
                if best_i is not None and best_score >= 5:
                    sp, sl = best_i, 0
                else:
                    sp, sl = max(0, int(total * 0.65)), 0

        ep = total - 1
        for i in range(sp + 1, total):
            for ln in clean_pages[i][:18]:
                if self.RE_FIN.match(ln['text'].strip()):
                    ep = i - 1
                    break
            if ep != total - 1 and i > ep:
                break

        ref_lines = []
        for i in range(sp, ep + 1):
            sj = sl if i == sp else 0
            if i == sp and sj < len(clean_pages[i]):
                if self.RE_HEADER.match(clean_pages[i][sj]['text'].strip()):
                    sj += 1
            ref_lines.extend(clean_pages[i][sj:])
        return ref_lines

    def _segmentar(self, ref_lines):
        if not ref_lines:
            return []

        xs = sorted([ln['x0'] for ln in ref_lines if ln['x0'] > 0])
        margen = xs[len(xs) // 10] if xs else 0
        SANGRIA = margen + 10

        cands, buf, prev = [], [], ''

        def flush():
            if not buf:
                return
            txt = re.sub(r'\s+', ' ', ' '.join(buf)).strip()
            tiene_anio = bool(re.search(r'\(\s*(?:(?:18|19|20)\d{2}[a-z]?(?:/[12]\d{3}[a-z]?)?|s\.f\.)\s*\)', txt, re.I))
            tiene_ancla = bool(re.search(r'10\.\d{4,9}/|https?://|www\.', txt, re.I))
            if 20 < len(txt) < 1800 and len(set(self.RE_ANIO.findall(txt))) <= 5:
                if (tiene_anio or tiene_ancla) and self._valida(txt):
                    cands.append(txt)
            buf.clear()

        for ln in ref_lines:
            raw = ln['text']
            x0 = ln['x0']

            raw = unicodedata.normalize('NFC', raw)
            raw = raw.replace('\ufb01', 'fi').replace('\ufb02', 'fl')
            raw = raw.replace('\u2013', '-').replace('\u2014', '-')

            is_bullet = bool(self.RE_VIETA.match(raw))
            clean = self.RE_VIETA.sub('', raw).strip()
            clean = re.sub(r'^[\"\'*\u201c\u201d\u2018\u2019\u201e\u2122]+', '', clean).strip()

            if not clean:
                continue
            if re.match(r'^\s*(lista de referencias|listado de referencias|referencias|bibliografía|bibliografia|references|reference list|\d{1,3})\s*$',
                        clean, re.IGNORECASE):
                continue

            if buf and prev.endswith('-'):
                buf[-1] = buf[-1][:-1] + clean
                prev = clean
                continue

            prev_txt = re.sub(r'\s+', ' ', ' '.join(buf[-2:])).strip() if buf else ''
            prev_sin_anio = bool(buf) and not self.RE_ANIO.search(prev_txt)
            prev_autores_abiertos = prev_sin_anio and (
                self.RE_AUTORES_SOLOS.search(prev_txt)
                or re.search(r'(?:,\s*[A-Z]\.\s*){3,}', prev_txt)
                or prev_txt.endswith(',')
            )
            curr_parece_continuacion = bool(self.RE_ANIO_INICIAL.search(clean)) or (
                not any(p.search(clean) for p in [self.RE_APA, self.RE_NUMERICO, self.RE_INSTITUCIONAL, self.RE_AUTOR])
            )

            es_nueva = False

            if any(p.search(clean) for p in [self.RE_APA, self.RE_NUMERICO, self.RE_INSTITUCIONAL, self.RE_AUTOR]):
                es_nueva = True

            if is_bullet and self.RE_ANIO.search(clean):
                es_nueva = True

            if prev_autores_abiertos and curr_parece_continuacion:
                es_nueva = False

            if buf and x0 <= SANGRIA and self.RE_AUTOR.search(clean):
                es_nueva = True

            if buf and x0 > SANGRIA + 5:
                if not any(p.search(clean) for p in [self.RE_APA, self.RE_NUMERICO]):
                    es_nueva = False

            if es_nueva:
                flush()
                buf.append(clean)
            else:
                buf.append(clean)

            prev = clean

        flush()
        return cands

    def _valida(self, texto):
        if re.match(r'^[a-záéíóúñ]', texto):
            return False
        if re.match(r'^Ap[eé]ndice\s+[A-Z\d]|^Anexo\s+[A-Z\d]', texto, re.I):
            return False
        if re.search(r'(\d+,\d+\s+\d+,\d+.*){2,}|p<\s*[.,]\d+|F\(\s*\d+|z\s+sig\b', texto, re.I):
            return False
        if re.search(r'\b(CFI|TLI|RMSEA|MLR|Maximum Likelihood|Modelo Original|indices? de ajuste|Tabla\s+\d+|Figura\s+\d+|AFC|AFE|Tamañ?o del efecto|Variables Psicosociales|Objetivo General|Descripci[oó]n Muestral|Comparaci[oó]n Intergrupos|Reacci[oó]n Emocional)\b', texto, re.I):
            return False

        tiene_biblio_fuerte = bool(re.search(
            r'10\.\d{4,9}/|https?://|www\.|'
            r'\b\d+\s*\(\d+\)\b|\b\d{1,4}\s*[-–]\s*\d{1,4}\b|'
            r'\b(Journal|Review|Revista|Archives|Psychology|Psychological|Psycho-Oncology|Psychotherapy|Oncology|Medicine|Brain|Cortex|Psychiatry|Contemporánea)\b',
            texto, re.I
        ))
        if re.match(r'^[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñüÜ\-\s]+(?:et al\.)?\s*\(\d{4}[a-z]?\)', texto):
            if re.search(r'\b(señaló|coincidieron|concluyeron|sostienen|propone|mostraron|explicó|indicó|reconocieron|se organizó|se encontró|configuraron|fueron los pocos ejemplos|concluyó|describieron|observaron|se focalizan|se impone)\b', texto, re.I) and not tiene_biblio_fuerte:
                return False

        if re.search(r'et al\.\s*\(\d{4}(?:;\s*\d{4})+\)', texto, re.I) and len(texto) > 180 and not tiene_biblio_fuerte:
            return False

        if re.match(r'^(Como |Según |Segun |Para |En una |En el |En la |Sin embargo|De acuerdo|Siguiendo|Complementariamente|Complementario|Durante |Al principio)', texto):
            if not re.search(r'[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+,\s+[A-Z]\.\s*\(\d{4}', texto):
                return False

        return any(p.search(texto) for p in [self.RE_APA, self.RE_NUMERICO, self.RE_INSTITUCIONAL, self.RE_AUTOR])

    def _contar_inicios_referencia(self, texto):
        if not isinstance(texto, str):
            return 0
        cand_pat = re.compile(
            r'(?=(?:^|(?<=\.\s))([A-ZÀ-ÖØ-Þ][^.]{0,180}?\(\d{4}[a-z]?\)\.))',
            flags=re.UNICODE
        )
        starts = []
        for m in cand_pat.finditer(texto):
            pos = m.start(1)
            if re.search(r'\(\d{4}[a-z]?\)', texto[pos:pos+900]):
                starts.append(pos)
        return len(sorted(set(starts)))

    def _es_probable_multireferencia(self, texto):
        if not isinstance(texto, str):
            return False
        t = re.sub(r'\s+', ' ', texto).strip()
        if not t:
            return False
        n_doi = len(re.findall(r'(?:https?://(?:dx\.)?doi\.org/|doi\s*:?\s*)(10\.\d{4,9}/[-._;()/:A-Z0-9]+)', t, flags=re.I))
        n_starts = self._contar_inicios_referencia(t)
        if n_doi >= 2:
            return True
        if n_starts >= 2 and len(t) > 260:
            return True
        if re.search(r'(?:https?://\S+|doi\s*:?\s*10\.\S+)\.?\s+(?=[A-ZÁÉÍÓÚÑ][^.]{0,420}?\(\d{4}[a-z]?\)\.)', t, flags=re.I | re.UNICODE):
            return True
        return False

    def _split_multireferencia(self, texto):
        if not isinstance(texto, str):
            return [texto]
        t = re.sub(r'\s+', ' ', texto).strip()
        if not t:
            return [texto]

        t = re.sub(
            r'((?:https?://\S+|doi\s*:?\s*10\.\S+)\.?)\s+(?=([A-ZÁÉÍÓÚÑ][^.]{0,420}?\(\d{4}[a-z]?\)\.))',
            r'\1<<<SPLIT>>>',
            t,
            flags=re.I | re.UNICODE
        )
        t = re.sub(
            r'\.\s+(?=([A-ZÁÉÍÓÚÑ][^.]{0,220}?\(\d{4}[a-z]?\)\.))',
            r'.<<<SPLIT>>>',
            t,
            flags=re.UNICODE
        )

        partes = [p.strip(' .') for p in t.split('<<<SPLIT>>>') if p.strip(' .')]
        if len(partes) <= 1:
            return [texto.strip()]

        out = []
        for p in partes:
            p = re.sub(r'\s+', ' ', p).strip()
            if p:
                if not p.endswith('.'):
                    p += '.'
                out.append(p)
        return out if out else [texto.strip()]

    def _clasificar_base(self, texto, revista_hint=None):
        t = texto.lower()
        if re.search(r'\b(tesis|dissertation|trabajo final|trabajo de grado)\b', t):
            return 'tesis'
        if re.search(r'\b(ley n|resolución|resolucion|decreto|boletín oficial|boletin oficial)\b', t):
            return 'documento_legal'
        if re.search(r'\ben\s+[A-Z].*?\((eds?|comps?|dirs?|orgs?)\.?\)', texto, re.I):
            return 'capitulo'
        if re.search(r'\b(congreso|conferencia|conference|simposio|symposium|jornadas)\b', t):
            return 'conferencia'
        if revista_hint and not candidato_no_es_revista(str(revista_hint)):
            return 'articulo_revista'
        if re.search(r',\s*\d+\s*\(\d+\)\s*,\s*\d{1,4}', texto):
            return 'articulo_revista'
        if re.search(r',\s*\d+\s*\(\d+\)', texto):
            return 'articulo_revista'
        if re.search(r',\s*\d{1,4}\s*[-–]\s*\d{1,4}', texto):
            return 'articulo_revista'
        if re.search(r',\s*\d+\s*,\s*\d{4,6}\b', texto):
            return 'articulo_revista'
        if re.search(r'10\.\d{4,9}/', texto) and REVISTA_CUE_RE_GLOBAL.search(texto):
            return 'articulo_revista'
        if REVISTA_CUE_RE_GLOBAL.search(texto):
            return 'articulo_revista'
        if re.search(r'\b(Universidad|University|Institute|Instituto|Department of|Departamento de|Ministry|Ministerio|National Center|Institute of Education Sciences|U\.S\. Department of Education)\b', texto, re.I):
            return 'documento_institucional'
        if re.search(r'https?://|www\.', texto, re.I):
            return 'recurso_web'
        return 'libro'

    def _extraer_revista_rescate(self, texto):
        if not isinstance(texto, str) or not texto.strip():
            return None
        t = re.sub(r'\s+', ' ', texto).strip()
        if not ARTICLE_CUE_RE.search(t):
            return None
        t = re.split(r'(?:https?://(?:dx\.)?doi\.org/\S+|https?://\S+|doi\s*:?\s*10\.\S+)', t, maxsplit=1, flags=re.I)[0].strip()
        patrones = [
            r'\)\.\s*(?P<titulo>.+?[\.!?])\s*(?P<revista>[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñüÜ&\-\.\s]{2,120}?),\s*\d+\s*\(\d+\)\s*,\s*\d{1,4}\s*[-–]\s*\d{1,4}\b',
            r'\)\.\s*(?P<titulo>.+?)\.\s*(?P<revista>[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñüÜ&\-\.\s]{2,120}?),\s*\d+\s*\(\d+\)\b',
            r'\)\.\s*(?P<titulo>.+?[\.!?])\s*(?P<revista>[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñüÜ&\-\.\s]{2,120}?),\s*\d{1,4}\s*[-–]\s*\d{1,4}\b',
            r'\)\.\s*(?P<titulo>.+?[\.!?])\s*(?P<revista>[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñüÜ&\-\.\s]{2,120}?),\s*\d+\s*,\s*\d{4,6}\b',
            r'\)\.\s*(?P<titulo>.+?[\.!?])\s*(?P<revista>[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñüÜ&\-\.\s]{2,120}?)\.\s*$',
            r'(?P<revista>(?:Jpn J Clin Oncol|Psycho-Oncology|Psychotherapy|Proceedings of the National Academy of Sciences|Cl[ií]nica Contempor[aá]nea|Nature Human Behaviour|Biological Psychiatry|Human Brain Mapping|Mental Health and Physical Activity|Computers in Human Behavior|Frontiers in Physiology|Psychology Research and Behavior Management|NeuroImage|BMC Research Notes|Cerebral Cortex|Brain))'
        ]
        for pat in patrones:
            m = re.search(pat, t, re.I)
            if m:
                cand = _norm_revista(m.group('revista').strip().rstrip('.,;'))
                if cand and 4 <= len(cand) <= 120 and len(cand.split()) <= 12 and not candidato_no_es_revista(cand):
                    return cand
        return None

    def _titulo_fuente(self, resto, tipo):
        if not resto:
            return '', ''
        resto = re.sub(r'\s+', ' ', resto).strip()
        resto_sin_doi = re.split(r'(?:https?://(?:dx\.)?doi\.org/\S+|https?://\S+|doi\s*:?\s*10\.\S+)', resto, maxsplit=1, flags=re.I)[0].strip()
        if tipo == 'articulo_revista':
            patrones = [
                r'^(?P<titulo>.+?[\.!?])\s*(?P<revista>[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñüÜ&\-\.\s]{2,120}?),\s*\d+\s*\(\d+\)\s*,\s*\d{1,4}\s*[-–]\s*\d{1,4}\b',
                r'^(?P<titulo>.+?)\.\s*(?P<revista>[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñüÜ&\-\.\s]{2,120}?),\s*\d+\s*\(\d+\)\b',
                r'^(?P<titulo>.+?[\.!?])\s*(?P<revista>[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñüÜ&\-\.\s]{2,120}?),\s*\d{1,4}\s*[-–]\s*\d{1,4}\b',
                r'^(?P<titulo>.+?[\.!?])\s*(?P<revista>[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñüÜ&\-\.\s]{2,120}?),\s*\d+\s*,\s*\d{4,6}\b',
                r'^(?P<titulo>.+?[\.!?])\s*(?P<revista>[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñüÜ&\-\.\s]{2,120}?)\.\s*$'
            ]
            for pat in patrones:
                m = re.search(pat, resto_sin_doi, re.I)
                if m:
                    titulo = m.group('titulo').strip()
                    titulo = titulo.rstrip() if titulo.endswith(('?', '!')) else titulo.rstrip('. ')
                    revista = _norm_revista(m.group('revista').strip().rstrip('.,; '))
                    if not candidato_no_es_revista(revista):
                        return titulo, revista
        partes = re.split(r'[\.!?]\s+', resto_sin_doi, maxsplit=1)
        titulo = partes[0].strip().rstrip('. ')
        fuente = partes[1].strip() if len(partes) > 1 else ''
        fuente = re.sub(r'https?://\S+', '', fuente).strip()
        fuente = re.sub(r'doi\s*:\s*10\.\S+', '', fuente, flags=re.I).strip()
        return titulo, fuente

    def _revista(self, texto, tipo):
        if tipo != 'articulo_revista':
            return None, None
        r = self._extraer_revista_rescate(texto)
        if r and not candidato_no_es_revista(r):
            return r, r.lower()
        return None, None

    def _parsear(self, texto):
        texto = re.sub(r'\s+', ' ', texto).strip()
        m = re.search(r'^([^(]+)\(\s*((?:19|20)\d{2}[a-z]?(?:/[12]\d{3}[a-z]?)?|s\.f\.)[^)]*\)\s*\.?', texto, re.I)
        if m:
            auts_raw = m.group(1).strip()
            anio = m.group(2).strip()
            resto = texto[m.end():].strip()
        else:
            mn = self.RE_NUMERICO.search(texto)
            anos = self.RE_ANIO.findall(texto)
            anio = anos[0] if anos else ''
            auts_raw = ''
            resto = texto[(mn.end() if mn else 0):].strip()
        rev_hint = self._extraer_revista_rescate(texto)
        tipo = self._clasificar_base(texto, revista_hint=rev_hint)
        es_rev = (tipo == 'articulo_revista')
        titulo, fuente = self._titulo_fuente(resto, tipo)
        rev_can, rev_norm = self._revista(texto, tipo)
        autor, auts_n = self._autores(auts_raw)
        if es_rev and rev_can:
            fuente = rev_can
        md = re.search(r'(10\.\d{4,9}/[^\s"<>]+)', texto, re.I)
        doi = md.group(1).rstrip('.,)') if md else None
        return {
            'autor_final': autor,
            'autores_normalizados': auts_n,
            'anio_edicion': anio,
            'tipo_documento': tipo,
            'es_revista': es_rev,
            'titulo': titulo,
            'revista_canonica': rev_can if es_rev else None,
            'revista_norm': rev_norm if es_rev else None,
            'fuente_editorial': fuente if not es_rev else None,
            'doi': doi,
            'cita_cruda': texto,
        }

    def _autores(self, raw):
        if not raw:
            return '', ''
        raw = re.sub(r'^[\d\.\-\s\[\]]+', '', raw).strip()
        t = raw
        t = re.sub(r',\s*&\s*|\s+&\s+', '||', t)
        t = re.sub(r'\s+\by\b\s+|\s+\band\b\s+', '||', t, flags=re.I)
        t = re.sub(r'\.,\s+', '.||', t)
        t = re.sub(r'\b(et al\.?|eds?\.?|comps?\.?|dirs?\.?|orgs?\.?)\b', '', t, flags=re.I)
        lista = [a.strip(' ,.') for a in t.split('||') if len(a.strip()) > 2]
        limpios = []
        for a in lista:
            vip = next((c for p, c in AUTORES_VIP.items() if re.search(p, a, re.I)), None)
            limpios.append(vip if vip else re.sub(r'\.([A-Z])', r'. \1', a).strip())
        return (limpios[0] if limpios else ''), ' | '.join(limpios)

    def procesar(self, pdf_path):
        clean, toc = self._extraer(pdf_path)
        if not clean:
            return []

        legible, motivo = self._pdf_legible(clean)
        if not legible:
            self.exclusiones.append({'id_tesis': pdf_path.stem, 'motivo_exclusion': motivo})
            logging.warning(f'PDF excluido por baja legibilidad: {pdf_path.name} | {motivo}')
            return []

        ref_lines = self._aislar(clean, toc)

        txt_path = self.out_refs_dir / f'{pdf_path.stem}_REFS.txt'
        with open(txt_path, 'w', encoding='utf-8') as f:
            for ln in ref_lines:
                f.write(ln['text'] + '\n')

        refs = self._segmentar(ref_lines)
        refs_expandidas = []
        for r in refs:
            partes = self._split_multireferencia(r) if self._es_probable_multireferencia(r) else [r]
            refs_expandidas.extend(partes)

        records = []
        for i, r in enumerate(refs_expandidas, 1):
            p = self._parsear(r)
            p['id_tesis'] = pdf_path.stem
            p['ref_uid'] = f'REF_{pdf_path.stem[:20]}_{i:04d}'
            p['probable_multireferencia'] = self._es_probable_multireferencia(r)
            records.append(p)
        return records

print('✅ Extractor V3.2.2 definido.')


# ════════════ CELDA 4 — Post-proceso integrado V3.2 ════════════════════════

def _norm_autor(n):
    if pd.isna(n) or str(n).strip() in ('', 'nan'):
        return None
    n = str(n).strip()
    if '|' in n:
        n = n.split('|')[0].strip().rstrip(',.')
    n = re.sub(r'\s*\[.*?\]', '', n).strip()
    if re.match(r'^[A-Z]\.\s*[A-Z]\.?$', n):
        return None
    n = re.sub(r'\s+', ' ', n).strip().rstrip(';,. ')
    return n if len(n) > 2 else None

def _norm_revista(r):
    if pd.isna(r) or str(r).strip() in ('', 'nan'):
        return None
    r = str(r).strip().rstrip('.')
    r = re.sub(r'https?://\S+', '', r).strip()
    r = re.sub(r'(?i)doi\s*:?\s*10\.\S+', '', r).strip()
    r = re.sub(r'\s+', ' ', r)
    fixes = {
        'Jpn J Clin Oncol': 'Jpn J Clin Oncol',
        'Psycho Oncology': 'Psycho-Oncology',
        'Clinica Contemporánea': 'Clínica Contemporánea',
        'Clínica Contemporanea': 'Clínica Contemporánea',
    }
    return fixes.get(r, r)

def _extraer_revista_rescate_global(texto):
    if pd.isna(texto):
        return None
    t = re.sub(r'\s+', ' ', str(texto)).strip()
    if not t or not ARTICLE_CUE_RE.search(t):
        return None
    t = re.split(r'(?:https?://(?:dx\.)?doi\.org/\S+|https?://\S+|doi\s*:?\s*10\.\S+)', t, maxsplit=1, flags=re.I)[0].strip()
    patrones = [
        r'\)\.\s*(?P<titulo>.+?[\.!?])\s*(?P<revista>[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñüÜ&\-\.\s]{2,120}?),\s*\d+\s*\(\d+\)\s*,\s*\d{1,4}\s*[-–]\s*\d{1,4}\b',
        r'\)\.\s*(?P<titulo>.+?)\.\s*(?P<revista>[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñüÜ&\-\.\s]{2,120}?),\s*\d+\s*\(\d+\)\b',
        r'\)\.\s*(?P<titulo>.+?[\.!?])\s*(?P<revista>[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñüÜ&\-\.\s]{2,120}?),\s*\d{1,4}\s*[-–]\s*\d{1,4}\b',
        r'\)\.\s*(?P<titulo>.+?[\.!?])\s*(?P<revista>[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñüÜ&\-\.\s]{2,120}?),\s*\d+\s*,\s*\d{4,6}\b',
        r'\)\.\s*(?P<titulo>.+?[\.!?])\s*(?P<revista>[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñüÜ&\-\.\s]{2,120}?)\.\s*$',
        r'(?P<revista>(?:Jpn J Clin Oncol|Psycho-Oncology|Psychotherapy|Proceedings of the National Academy of Sciences|Cl[ií]nica Contempor[aá]nea|Nature Human Behaviour|Biological Psychiatry|Human Brain Mapping|Mental Health and Physical Activity|Computers in Human Behavior|Frontiers in Physiology|Psychology Research and Behavior Management|NeuroImage|BMC Research Notes|Cerebral Cortex|Brain))'
    ]
    for pat in patrones:
        m = re.search(pat, t, re.I)
        if m:
            cand = _norm_revista(m.group('revista').strip().rstrip('.,;'))
            if cand and 4 <= len(cand) <= 120 and len(cand.split()) <= 12 and not candidato_no_es_revista(cand):
                return cand
    return None

def _titulo_y_fuente_recalculados(cita, tipo):
    if pd.isna(cita):
        return '', ''
    resto = re.sub(r'^([^(]+)\(\s*((?:19|20)\d{2}[a-z]?(?:/[12]\d{3}[a-z]?)?|s\.f\.)[^)]*\)\s*\.?', '', str(cita), flags=re.I)
    resto = re.sub(r'\s+', ' ', resto).strip()
    resto = re.split(r'(?:https?://(?:dx\.)?doi\.org/\S+|https?://\S+|doi\s*:?\s*10\.\S+)', resto, maxsplit=1, flags=re.I)[0].strip()
    if tipo == 'articulo_revista':
        patrones = [
            r'^(?P<titulo>.+?[\.!?])\s*(?P<revista>[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñüÜ&\-\.\s]{2,120}?),\s*\d+\s*\(\d+\)\s*,\s*\d{1,4}\s*[-–]\s*\d{1,4}\b',
            r'^(?P<titulo>.+?)\.\s*(?P<revista>[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñüÜ&\-\.\s]{2,120}?),\s*\d+\s*\(\d+\)\b',
            r'^(?P<titulo>.+?[\.!?])\s*(?P<revista>[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñüÜ&\-\.\s]{2,120}?),\s*\d{1,4}\s*[-–]\s*\d{1,4}\b',
            r'^(?P<titulo>.+?[\.!?])\s*(?P<revista>[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñüÜ&\-\.\s]{2,120}?),\s*\d+\s*,\s*\d{4,6}\b',
            r'^(?P<titulo>.+?[\.!?])\s*(?P<revista>[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñüÜ&\-\.\s]{2,120}?)\.\s*$'
        ]
        for pat in patrones:
            m = re.search(pat, resto, re.I)
            if m:
                titulo = m.group('titulo').strip()
                titulo = titulo.rstrip() if titulo.endswith(('?', '!')) else titulo.rstrip('. ')
                revista = _norm_revista(m.group('revista').strip().rstrip('.,;'))
                if not candidato_no_es_revista(revista):
                    return titulo, revista
    partes = re.split(r'[\.!?]\s+', resto, maxsplit=1)
    titulo = partes[0].strip().rstrip('. ')
    fuente = partes[1].strip() if len(partes) > 1 else ''
    fuente = re.sub(r'https?://\S+', '', fuente).strip()
    fuente = re.sub(r'(?i)doi\s*:?\s*10\.\S+', '', fuente).strip()
    return titulo, fuente

def _es_multireferencia_residual(texto):
    if pd.isna(texto):
        return False
    t = re.sub(r'\s+', ' ', str(texto)).strip()
    n_doi = len(re.findall(r'(?:https?://(?:dx\.)?doi\.org/|doi\s*:?\s*)(10\.\d{4,9}/[-._;()/:A-Z0-9]+)', t, flags=re.I))
    n_starts = len(re.findall(r'(?=(?:^|(?<=\.\s))[^.]{0,420}?\(\d{4}[a-z]?\)\.)', t, flags=re.UNICODE))
    if n_doi >= 2:
        return True
    if n_starts >= 2 and len(t) > 260:
        return True
    return False

def _clasificar_final(cita, revista_canonica=None):
    if pd.isna(cita):
        return 'sin_clasificar'
    r = str(cita)
    if re.search(r'\b(tesis|dissertation|trabajo final|trabajo de grado)\b', r, re.I):
        return 'tesis'
    if re.search(r'\b(Congreso|Conferencia|Conference|Simposio|Symposium|Jornadas)\b', r, re.I):
        return 'conferencia'
    if re.search(r'\b(Ley N|Decreto|Resolución|Resolucion|Boletín Oficial|Boletin Oficial)\b', r, re.I):
        return 'documento_legal'
    if re.search(r'\b(En\s|In\s)[A-Z]', r) and re.search(r'\((?:Ed\.|Eds\.|Comp\.|Comps\.|Dir\.|Dirs\.)\)', r):
        return 'capitulo'
    if revista_canonica and str(revista_canonica).strip() not in ('', 'None', 'nan') and not candidato_no_es_revista(str(revista_canonica)):
        return 'articulo_revista'
    if re.search(r',\s*\d+\s*\(\d+\)\s*,\s*\d{1,4}', r):
        return 'articulo_revista'
    if re.search(r',\s*\d+\s*\(\d+\)', r):
        return 'articulo_revista'
    if re.search(r',\s*\d{1,4}\s*[-–]\s*\d{1,4}\b', r):
        return 'articulo_revista'
    if re.search(r',\s*\d+\s*,\s*\d{4,6}\b', r):
        return 'articulo_revista'
    if re.search(r'10\.\d{4,9}/', r) and REVISTA_CUE_RE_GLOBAL.search(r):
        return 'articulo_revista'
    if re.search(r'\b(Universidad|University|Institute|Instituto|Department of|Departamento de|Ministry|Ministerio|National Center|Institute of Education Sciences|U\.S\. Department of Education)\b', r, re.I):
        return 'documento_institucional'
    if re.search(r'\b(Paidós|Siglo XXI|Amorrortu|Nueva Visión|Gedisa|Herder|Springer|Wiley|Oxford|Cambridge|Guilford|Erlbaum|Sage|Routledge|Pearson|Fondo de Cultura|Alianza|Anagrama|Planeta|Manantial|Biblos|Katz|Morata|Trotta|Ariel|Lumen|Granica)\b', r, re.I):
        return 'libro'
    if re.search(r'https?://|www\.', r, re.I):
        return 'recurso_web'
    return 'sin_clasificar'

def postprocesar(df):
    print(f'  Entrantes:  {len(df)}')
    df = df.drop_duplicates(subset=['id_tesis', 'cita_cruda'], keep='first').copy()
    df['cita_cruda'] = df['cita_cruda'].astype(str).str.replace(r'\s+', ' ', regex=True).str.strip()
    df['longitud'] = df['cita_cruda'].str.len()
    df = df[(df['longitud'] >= 30) & (df['longitud'] <= 1200)].copy()
    df['motivo_filtrado'] = None

    mask_ruido = df['cita_cruda'].str.contains(
        r'(?:\d+,\d+\s+\d+,\d+.*){2,}|p<\s*[.,]\d+|F\(\s*\d+|z\s+sig\b|veces por semana|veces al mes|PUNTAJE TOTAL|Consentimiento|Ap[eé]ndice [A-Z]\.|Anexo [A-Z]\.|α\s*=|Objetivo General|Descripci[oó]n Muestral|Distribuci[oó]n Inicial|Comparaci[oó]n Intergrupos|Reacci[oó]n Emocional:|Activaci[oó]n Emocional;|Ecuaciones Estructurales|An[aá]lisis Factorial|CFI\b|TLI\b|RMSEA\b',
        regex=True, case=False, na=False
    )
    df.loc[mask_ruido, 'motivo_filtrado'] = 'ruido_estadistico_o_tabla'

    mask_narrativo = df['cita_cruda'].str.contains(
        r'\b(señaló|coincidieron|concluyeron|sostienen|sostuvo|propone|propuso|mostraron|muestra|explicó|explica|indicó|indican|reconocieron|se organizó|se encontró|configuraron|fueron los pocos ejemplos|concluyó|describieron|observaron|se focalizan|se impone)\b',
        regex=True, case=False, na=False
    ) & ~df['cita_cruda'].str.contains(
        r'10\.\d{4,9}/|https?://|\b\d+\s*\(\d+\)|\b\d{1,4}\s*[-–]\s*\d{1,4}\b',
        regex=True, case=False, na=False
    )
    df.loc[mask_narrativo & df['motivo_filtrado'].isna(), 'motivo_filtrado'] = 'falso_positivo_narrativo'

    mask_multi = df['cita_cruda'].apply(_es_multireferencia_residual)
    df.loc[mask_multi & df['motivo_filtrado'].isna(), 'motivo_filtrado'] = 'multireferencia_residual'

    df_filtradas = df[df['motivo_filtrado'].notna()].copy()
    df = df[df['motivo_filtrado'].isna()].copy()

    df['autor_final'] = df['autor_final'].apply(_norm_autor)

    mask_rev_empty = df['revista_canonica'].isna() | (df['revista_canonica'].astype(str).str.strip().isin(['', 'None', 'nan']))
    mask_intentar_rescate = (
        mask_rev_empty &
        df['cita_cruda'].astype(str).str.contains(
            r'(\b\d+\(\d+\)\b|\b\d{1,4}\s*[-–]\s*\d{1,4}\b|10\.\d{4,9}/)',
            regex=True, na=False
        ) &
        ~df['cita_cruda'].astype(str).str.contains(
            r'\b(En\s+.+\((?:Ed\.|Eds\.|Comp\.|Comps\.)\)|tesis|dissertation|archivo digital|repositorio|repository|oxford university press|cambridge university press|routledge|springer|academic press|guilford press|editorial|manual moderno|universidad nacional|facultad de|u\.s\. department of education)\b',
            regex=True, case=False, na=False
        )
    )

    if 'revista_rescate' not in df.columns:
        df['revista_rescate'] = None

    df.loc[mask_intentar_rescate, 'revista_rescate'] = df.loc[mask_intentar_rescate, 'cita_cruda'].apply(_extraer_revista_rescate_global)
    df.loc[df['revista_rescate'].notna(), 'revista_canonica'] = df.loc[df['revista_rescate'].notna(), 'revista_rescate']

    df['revista_canonica'] = df['revista_canonica'].apply(_norm_revista)
    bad_mask = df['revista_canonica'].apply(lambda x: candidato_no_es_revista(x) if isinstance(x, str) else False)
    df.loc[bad_mask, 'revista_canonica'] = None

    df['revista_norm'] = df['revista_canonica'].apply(lambda x: x.lower() if isinstance(x, str) and x.strip() else None)
    tipos = df.apply(lambda row: _clasificar_final(row.get('cita_cruda', ''), row.get('revista_canonica', None)), axis=1)
    recalculados = df.apply(lambda row: _titulo_y_fuente_recalculados(row.get('cita_cruda', ''), tipos.loc[row.name]), axis=1)
    df['titulo'] = [t for t, f in recalculados]
    df['fuente_editorial'] = [f for t, f in recalculados]
    df['tipo_documento'] = tipos
    df['es_revista'] = df['tipo_documento'].eq('articulo_revista')
    df.loc[df['es_revista'], 'fuente_editorial'] = None
    df.loc[~df['es_revista'], 'revista_norm'] = None
    print(f'  Filtradas:  {len(df_filtradas)}')
    print(f'  Finales:    {len(df)}')
    return df, df_filtradas

print('✅ Post-proceso V3.2.2 definido.')


# ════════════ CELDA 5 — Orquestador principal V3.2 ════════════════════════

from google.colab import files

CARPETA_CORPUS    = '/content/corpus_tesis'
CARPETA_REFS_TXT  = '/content/corpus_refs_txt'
ARCHIVO_SALIDA    = '/content/BASE_BIBLIOMETRICA_V3_2_2.csv'
ARCHIVO_EXCLUIDOS = '/content/pdfs_excluidos_v322.csv'
ARCHIVO_FILTRADAS = '/content/filas_filtradas_v322.csv'

os.makedirs(CARPETA_CORPUS,   exist_ok=True)
os.makedirs(CARPETA_REFS_TXT, exist_ok=True)

zips = [z for z in Path('/content').glob('*.zip') if 'BASE_BIBLIOMETRICA' not in z.name]
if zips:
    print(f'Descomprimiendo {zips[0].name}...')
    os.system(f'unzip -o -q "{zips[0]}" -d "{CARPETA_CORPUS}"')
    for pdf in Path(CARPETA_CORPUS).rglob('*.pdf'):
        if pdf.parent != Path(CARPETA_CORPUS):
            dest = Path(CARPETA_CORPUS) / pdf.name
            if not dest.exists():
                shutil.move(str(pdf), str(dest))
    print('Listo.')

pdfs = [p for p in list(Path(CARPETA_CORPUS).glob('*.pdf')) + list(Path(CARPETA_CORPUS).glob('*.PDF'))
        if p.stat().st_size > 100_000]

if not pdfs:
    print('ERROR: no hay PDFs. Subí tu ZIP y corré de nuevo.')
else:
    print(f'\nProcesando {len(pdfs)} tesis...\n')
    extractor = ExtractorV32(out_refs_dir=CARPETA_REFS_TXT)
    all_records = []

    for pdf_path in tqdm(pdfs, desc='Extrayendo'):
        try:
            records = extractor.procesar(pdf_path)
            all_records.extend(records)
            print(f'  {pdf_path.name}: {len(records)} refs')
        except Exception as e:
            print(f'  ERROR en {pdf_path.name}: {e}')

    if all_records:
        df_raw = pd.DataFrame(all_records)
        print('\nPost-proceso...')
        df_final, df_filtradas = postprocesar(df_raw)

        COLS = ['id_tesis','ref_uid','autor_final','autores_normalizados',
                'anio_edicion','tipo_documento','es_revista',
                'revista_canonica','revista_norm','titulo',
                'fuente_editorial','doi','revista_rescate','probable_multireferencia','longitud','cita_cruda']
        df_final = df_final[[c for c in COLS if c in df_final.columns]]

        df_final.to_csv(ARCHIVO_SALIDA, index=False, sep=';', encoding='utf-8-sig')
        if len(df_filtradas):
            df_filtradas.to_csv(ARCHIVO_FILTRADAS, index=False, sep=';', encoding='utf-8-sig')

        if extractor.exclusiones:
            pd.DataFrame(extractor.exclusiones).drop_duplicates().to_csv(
                ARCHIVO_EXCLUIDOS, index=False, sep=';', encoding='utf-8-sig'
            )
            print('\nPDFs excluidos por baja legibilidad:')
            display(pd.DataFrame(extractor.exclusiones).drop_duplicates())

        print(f'\nTotal: {len(df_final)} refs en {df_final["id_tesis"].nunique()} tesis')
        if len(df_filtradas):
            print('\nMotivos de filtrado narrativo/ruido:')
            display(df_filtradas['motivo_filtrado'].value_counts().reset_index())

        display(df_final['tipo_documento'].value_counts().reset_index())
        display(df_final[['id_tesis','autor_final','anio_edicion','tipo_documento',
                          'revista_canonica','cita_cruda']].sample(min(10, len(df_final)), random_state=42))

        try:
            files.download(ARCHIVO_SALIDA)
        except:
            print(f'Descarga manual: {ARCHIVO_SALIDA}')


# ════════════ CELDA 6 — Auditoría: ver TXT de una tesis ════════════════════

TESIS_AUDITAR = 'nombre_parcial'   # <- cambiá esto
txt_files = list(Path(CARPETA_REFS_TXT).glob(f'*{TESIS_AUDITAR}*'))
if txt_files:
    with open(txt_files[0], 'r', encoding='utf-8') as f:
        print(f.read()[:3000])
else:
    print('No encontrado.')


# ════════════ CELDA 7 — Diagnóstico de una tesis ═══════════════════════════

TESIS_DIAG = 'nombre_parcial'   # <- cambiá esto
subset = df_final[df_final['id_tesis'].str.contains(TESIS_DIAG, case=False)]
print(f'Total: {len(subset)}')
print(subset['tipo_documento'].value_counts())
print('\n--- Más cortas (posibles truncadas) ---')
display(subset.nsmallest(min(10, len(subset)), 'longitud')[['longitud','autor_final','cita_cruda']])
print('\n--- Más largas (posibles pegadas) ---')
display(subset.nlargest(min(5, len(subset)), 'longitud')[['longitud','autor_final','cita_cruda']])


# ════════════ CELDA 8 — Auditoría de rescates y filtradas ══════════════════

if 'df_filtradas' in globals() and len(df_filtradas):
    print('--- Filtradas ---')
    display(df_filtradas[['id_tesis','motivo_filtrado','cita_cruda']].head(20))

if 'df_final' in globals() and 'revista_rescate' in df_final.columns:
    resc = df_final[df_final['revista_rescate'].notna()].copy()
    print(f'--- Revistas rescatadas: {len(resc)} ---')
    if len(resc):
        display(resc[['id_tesis','tipo_documento','revista_canonica','revista_rescate','cita_cruda']].head(20))
