import re
import os
import csv
import hashlib
import json
from typing import List, Dict, Any, Tuple, Optional
import pdfplumber
from pypdf import PdfReader


class PDFSentenceParser:
    """
    Ingests text-based RFP PDFs, extracts structured sections,
    splits text into discrete clauses/sentences, assigns deterministic sentence IDs,
    computes bounding boxes (bbox) for visual audit, and tags element_type.
    """

    PARSER_VERSION = "v1.0"

    # Headings commonly found in PPRA / e-PADS / Standard Bidding Documents
    SECTION_HEADING_PATTERNS = [
        re.compile(r'^(?:SECTION|PART|CHAPTER|SCHEDULE|ANNEXURE|APPENDIX)\s+[0-9IVXLCDM]+[:\.\-]?\s*.*$', re.IGNORECASE),
        re.compile(r'^(?:INVITATION\s+FOR\s+BIDS|INSTRUCTIONS\s+TO\s+BIDDERS|BID\s+DATA\s+SHEET|GENERAL\s+CONDITIONS|SPECIAL\s+CONDITIONS|TECHNICAL\s+SPECIFICATIONS|SCOPE\s+OF\s+WORK|TERMS\s+OF\s+REFERENCE|EVALUATION\s+CRITERIA|ELIGIBILITY\s+CRITERIA|MANDATORY\s+REQUIREMENTS|COMMERCIAL\s+TERMS).*$', re.IGNORECASE),
        re.compile(r'^\d+\.\s+[A-Z\s]{4,}.*$'),  # e.g. "1. INVITATION FOR BIDS"
    ]

    # Specific known CID mappings
    KNOWN_CID_MAP = {
        "(cid:127)": "•",
        "(cid:128)": "•",
        "(cid:129)": "•",
        "(cid:147)": '"',
        "(cid:148)": '"',
        "(cid:145)": "'",
        "(cid:146)": "'",
        "(cid:150)": "-",
        "(cid:151)": "—",
    }

    # Abbreviations protected from false splits
    ABBREVIATIONS = {
        'e.g.', 'i.e.', 'etc.', 'vs.', 'mr.', 'ms.', 'dr.', 'prof.', 'sr.', 'no.',
        'nos.', 'ref.', 'sec.', 'art.', 'para.', 'ppra.', 'fbr.', 'ntn.', 'strn.',
        'pkr.', 'rs.', 'ltd.', 'pvt.', 'inc.', 'corp.', 'dept.', 'govt.', 'co.', 'vol.',
        'min.', 'max.', 'approx.', 'est.', 'cl.', 'itb.', 'bds.', 'srfp.', 'sbd.', 'qcbs.'
    }

    # Header/Footer lines to ignore
    HEADER_FOOTER_PATTERNS = [
        re.compile(r'^page\s+\d+(\s+of\s+\d+)?$', re.IGNORECASE),
        re.compile(r'^tender\s+reference\s+no\..*$', re.IGNORECASE),
        re.compile(r'^rfp\s*#.*$', re.IGNORECASE),
    ]

    def __init__(self, top_margin: float = 40.0, bottom_margin: float = 40.0):
        self.top_margin = top_margin
        self.bottom_margin = bottom_margin
        self.unknown_cid_count = 0
        self.unknown_cids_found = set()

    @staticmethod
    def compute_sha256(file_path: str) -> str:
        """Computes SHA-256 hash of a file."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    def parse_pdf(self, pdf_path: str, tender_id: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Parses a PDF into section-tagged, bbox-annotated candidate sentences.
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found at: {pdf_path}")

        pdf_sha256 = self.compute_sha256(pdf_path)
        self.unknown_cid_count = 0
        self.unknown_cids_found = set()

        sentences = []
        current_section = "GENERAL"
        page_sentence_counters: Dict[int, int] = {}
        pages_processed = 0

        # Buffer for sentence assembly across lines and page breaks
        # Holds list of dicts: {"text": str, "raw_text": str, "page": int, "bbox": [x0, top, x1, bottom], "is_table": bool}
        active_buffer: List[Dict[str, Any]] = []

        def flush_buffer() -> None:
            nonlocal active_buffer, current_section, sentences
            if not active_buffer:
                return

            # Page break rule: sentence belongs to the page where it STARTED
            start_page = active_buffer[0]["page"]
            is_table = any(item.get("is_table", False) for item in active_buffer)

            # Combined raw text
            combined_raw = " ".join(item["raw_text"] for item in active_buffer).strip()

            # Combined bounding box for words on the start page
            start_page_items = [item for item in active_buffer if item["page"] == start_page]
            if start_page_items:
                x0 = min(item["bbox"][0] for item in start_page_items)
                top = min(item["bbox"][1] for item in start_page_items)
                x1 = max(item["bbox"][2] for item in start_page_items)
                bottom = max(item["bbox"][3] for item in start_page_items)
                combined_bbox = [round(x0, 1), round(top, 1), round(x1, 1), round(bottom, 1)]
            else:
                combined_bbox = [0.0, 0.0, 0.0, 0.0]

            active_buffer.clear()

            # Split combined text into discrete clauses/sentences
            sub_segments = self._split_segment_carefully(combined_raw)
            for seg in sub_segments:
                clean_seg = self._clean_known_cids_and_track_unknown(seg)
                clean_seg = self._normalize_clean_text(clean_seg)

                if len(clean_seg) >= 10:  # Ignore trivial noise
                    sent_num = page_sentence_counters.get(start_page, 1)
                    sentence_id = f"{tender_id}_p{start_page:02d}_s{sent_num:03d}"
                    page_sentence_counters[start_page] = sent_num + 1

                    elem_type = "table_row" if is_table else "sentence"

                    sentences.append({
                        "sentence_id": sentence_id,
                        "tender_id": tender_id,
                        "pdf_sha256": pdf_sha256,
                        "parser_version": self.PARSER_VERSION,
                        "page": start_page,
                        "element_type": elem_type,
                        "section": current_section,
                        "bbox": json.dumps(combined_bbox),
                        "text": clean_seg,
                        "raw_text": seg.strip(),
                        "type": "",
                        "mandatory": "",
                        "knockout": "",
                        "knockout_type": "",
                        "scored_criterion": "",
                        "marks": "",
                        "notes": ""
                    })

        try:
            with pdfplumber.open(pdf_path) as pdf:
                pages_processed = len(pdf.pages)
                for page_idx, page in enumerate(pdf.pages, start=1):
                    page_height = float(page.height)
                    page_width = float(page.width)

                    # Table bounding boxes on this page
                    table_bboxes = []
                    try:
                        tables = page.find_tables()
                        table_bboxes = [t.bbox for t in tables]
                    except Exception:
                        pass

                    # Extract words with geometry
                    words = page.extract_words(keep_blank_chars=False)

                    # Group words into visual lines by vertical alignment
                    visual_lines = self._group_words_into_lines(words, page_height, page_width)

                    for line_item in visual_lines:
                        line_text = line_item["text"].strip()
                        if not line_text:
                            continue

                        # Check header/footer noise
                        if self._is_header_or_footer(line_text):
                            continue

                        # Check if line intersects any table
                        line_bbox = line_item["bbox"]
                        is_in_table = self._is_bbox_in_tables(line_bbox, table_bboxes)

                        # Check if line indicates a section heading
                        if self._is_section_heading(line_text) and not is_in_table:
                            flush_buffer()
                            current_section = self._clean_heading(line_text)
                            # Add heading element
                            sent_num = page_sentence_counters.get(page_idx, 1)
                            sentence_id = f"{tender_id}_p{page_idx:02d}_s{sent_num:03d}"
                            page_sentence_counters[page_idx] = sent_num + 1

                            sentences.append({
                                "sentence_id": sentence_id,
                                "tender_id": tender_id,
                                "pdf_sha256": pdf_sha256,
                                "parser_version": self.PARSER_VERSION,
                                "page": page_idx,
                                "element_type": "heading",
                                "section": current_section,
                                "bbox": json.dumps([round(c, 1) for c in line_bbox]),
                                "text": current_section,
                                "raw_text": line_text,
                                "type": "",
                                "mandatory": "",
                                "knockout": "",
                                "knockout_type": "",
                                "scored_criterion": "",
                                "marks": "",
                                "notes": ""
                            })
                            continue

                        # Check if line starts a new numbered clause or bullet
                        if self._is_line_start_clause(line_text):
                            flush_buffer()
                            active_buffer.append({
                                "text": line_text,
                                "raw_text": line_text,
                                "page": page_idx,
                                "bbox": line_bbox,
                                "is_table": is_in_table
                            })
                        else:
                            # Check inline colon-separated clause
                            colon_parts = self._split_on_colon_clause(line_text)
                            if len(colon_parts) > 1:
                                flush_buffer()
                                for idx, part in enumerate(colon_parts):
                                    active_buffer.append({
                                        "text": part,
                                        "raw_text": part,
                                        "page": page_idx,
                                        "bbox": line_bbox,
                                        "is_table": is_in_table
                                    })
                                    if idx < len(colon_parts) - 1:
                                        flush_buffer()
                            else:
                                active_buffer.append({
                                    "text": line_text,
                                    "raw_text": line_text,
                                    "page": page_idx,
                                    "bbox": line_bbox,
                                    "is_table": is_in_table
                                })

                    # Page boundary rule:
                    # Flush buffer if items are in a table or if sentence ends with terminal punctuation
                    if active_buffer:
                        last_raw = active_buffer[-1]["raw_text"].strip()
                        is_tab = any(item.get("is_table", False) for item in active_buffer)
                        if is_tab or last_raw.endswith(('.', '!', '?', ':', ';')):
                            flush_buffer()

                flush_buffer()

        except Exception as e:
            # Fallback for corrupted or non-standard documents
            sentences, pages_processed = self._fallback_parse_pypdf(pdf_path, tender_id, pdf_sha256)

        meta = {
            "tender_id": tender_id,
            "pdf_sha256": pdf_sha256,
            "parser_version": self.PARSER_VERSION,
            "pages": pages_processed,
            "total_candidates": len(sentences),
            "element_counts": {
                "sentence": sum(1 for s in sentences if s["element_type"] == "sentence"),
                "table_row": sum(1 for s in sentences if s["element_type"] == "table_row"),
                "heading": sum(1 for s in sentences if s["element_type"] == "heading")
            },
            "unknown_cid_count": self.unknown_cid_count,
            "unknown_cids": list(self.unknown_cids_found)
        }

        return sentences, meta

    def _group_words_into_lines(self, words: List[Dict[str, Any]], page_height: float, page_width: float) -> List[Dict[str, Any]]:
        """
        Groups words into visual lines and computes line bboxes, respecting page margins.
        """
        usable_words = [
            w for w in words
            if self.top_margin <= w["top"] <= (page_height - self.bottom_margin)
        ]
        if not usable_words:
            return []

        usable_words.sort(key=lambda w: (w["top"], w["x0"]))

        lines = []
        current_line_words = [usable_words[0]]

        for w in usable_words[1:]:
            prev_w = current_line_words[-1]
            # If word is vertically close to the current line (within 4 points)
            if abs(w["top"] - prev_w["top"]) <= 4.0:
                current_line_words.append(w)
            else:
                lines.append(self._build_line_record(current_line_words))
                current_line_words = [w]

        if current_line_words:
            lines.append(self._build_line_record(current_line_words))

        return lines

    def _build_line_record(self, words: List[Dict[str, Any]]) -> Dict[str, Any]:
        words.sort(key=lambda w: w["x0"])
        text = " ".join(w["text"] for w in words)
        x0 = min(w["x0"] for w in words)
        top = min(w["top"] for w in words)
        x1 = max(w["x1"] for w in words)
        bottom = max(w["bottom"] for w in words)
        return {
            "text": text,
            "bbox": [x0, top, x1, bottom]
        }

    def _is_bbox_in_tables(self, bbox: List[float], table_bboxes: List[Tuple[float, float, float, float]]) -> bool:
        line_cx = (bbox[0] + bbox[2]) / 2.0
        line_cy = (bbox[1] + bbox[3]) / 2.0
        for tx0, ttop, tx1, tbottom in table_bboxes:
            if tx0 <= line_cx <= tx1 and ttop <= line_cy <= tbottom:
                return True
        return False

    def _clean_known_cids_and_track_unknown(self, text: str) -> str:
        def replace_cid(match):
            cid_str = match.group(0)
            if cid_str in self.KNOWN_CID_MAP:
                return self.KNOWN_CID_MAP[cid_str]
            else:
                self.unknown_cid_count += 1
                self.unknown_cids_found.add(cid_str)
                return cid_str

        return re.sub(r'\(cid:\d+\)', replace_cid, text)

    def _is_header_or_footer(self, line: str) -> bool:
        line_clean = line.strip().lower()
        for pat in self.HEADER_FOOTER_PATTERNS:
            if pat.match(line_clean):
                return True
        return False

    def _is_section_heading(self, line: str) -> bool:
        line_clean = line.strip()
        for pat in self.SECTION_HEADING_PATTERNS:
            if pat.match(line_clean):
                return True
        return False

    def _clean_heading(self, line: str) -> str:
        clean = re.sub(r'[\s:\-]+$', '', line.strip())
        return clean[:100]

    def _is_line_start_clause(self, line: str) -> bool:
        line_clean = line.strip()
        patterns = [
            r'^[•\-\*]\s+',
            r'^\(cid:127\)\s*',
            r'^\d+(\.\d+)+\.?\s+',              # 1.1, 2.3.4
            r'^\d+[\.\)]\s+[A-Z]',               # 1. The bidder..., 1) The job..., 10) Vendor...
            r'^\d+\s+[A-Z]{2,}',                 # 7 CABLE, 10 ELBOW, 18 STEEL
            r'^\([a-zA-Z0-9ivxLCDM]+\)\s+[A-Z]', # (a) Bids shall..., (1) The...
            r'^[a-zA-Z]\)\s+[A-Z]',             # a) Bids shall...
        ]
        for pat in patterns:
            if re.match(pat, line_clean):
                return True
        return False

    def _split_on_colon_clause(self, line: str) -> List[str]:
        colon_clause_pattern = re.compile(
            r':\s+(?:[•\-\*]|\(cid:127\))?\s*(?=(?:\d+(?:\.\d+)+\.?\s+[A-Z]|\([a-zA-Z0-9]+\)\s+[A-Z]))'
        )
        parts = colon_clause_pattern.split(line)
        if len(parts) > 1:
            results = []
            for i, part in enumerate(parts):
                if i == 0:
                    results.append(part.strip() + ":")
                else:
                    results.append(part.strip())
            return results
        return [line]

    def _split_segment_carefully(self, text: str) -> List[str]:
        protected_text = text

        for abbr in self.ABBREVIATIONS:
            pattern = re.compile(re.escape(abbr), re.IGNORECASE)
            protected_text = pattern.sub(lambda m: m.group(0).replace('.', '@@DOT@@'), protected_text)

        protected_text = re.sub(r'(\d+)\.(\d+)', r'\1@@DOT@@\2', protected_text)
        protected_text = re.sub(r'(Rs|No|Ref|Vol|cl|sec)\.\s+(\d+)', lambda m: f"{m.group(1)}@@DOT@@ {m.group(2)}", protected_text, flags=re.IGNORECASE)

        sentence_end = re.compile(r'([.?!])\s+(?=[A-Z0-9•\-\(])')
        tokens = sentence_end.split(protected_text)

        sentences = []
        for i in range(0, len(tokens), 2):
            part = tokens[i]
            punct = tokens[i+1] if i + 1 < len(tokens) else ""
            sent = (part + punct).replace('@@DOT@@', '.').strip()
            if sent:
                sentences.append(sent)

        return sentences

    def _normalize_clean_text(self, text: str) -> str:
        text = re.sub(r'\s+', ' ', text).strip()
        text = re.sub(r'^[•\-\*]\s*', '', text).strip()
        return text

    def _fallback_parse_pypdf(self, pdf_path: str, tender_id: str, pdf_sha256: str) -> Tuple[List[Dict[str, Any]], int]:
        sentences = []
        reader = PdfReader(pdf_path)
        for page_idx, page in enumerate(reader.pages, start=1):
            raw = page.extract_text() or ""
            lines = [l.strip() for l in raw.splitlines() if len(l.strip()) >= 10]
            for s_idx, l in enumerate(lines, start=1):
                sentences.append({
                    "sentence_id": f"{tender_id}_p{page_idx:02d}_s{s_idx:03d}",
                    "tender_id": tender_id,
                    "pdf_sha256": pdf_sha256,
                    "parser_version": self.PARSER_VERSION,
                    "page": page_idx,
                    "element_type": "sentence",
                    "section": "GENERAL",
                    "bbox": json.dumps([0.0, 0.0, 0.0, 0.0]),
                    "text": l,
                    "raw_text": l,
                    "type": "",
                    "mandatory": "",
                    "knockout": "",
                    "knockout_type": "",
                    "scored_criterion": "",
                    "marks": "",
                    "notes": ""
                })
        return sentences, len(reader.pages)

    @staticmethod
    def save_to_csv(sentences: List[Dict[str, Any]], output_path: str):
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        fieldnames = [
            "sentence_id", "tender_id", "pdf_sha256", "parser_version",
            "page", "element_type", "section", "bbox",
            "text", "raw_text", "type", "mandatory", "knockout",
            "knockout_type", "scored_criterion", "marks", "notes"
        ]
        with open(output_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for s in sentences:
                writer.writerow(s)
        print(f"Saved {len(sentences)} candidates to {output_path}")

    def parse(self, pdf_path: str, tender_id: str, use_llm_assist: bool = False) -> Dict[str, Any]:
        """
        Convenience wrapper returning structured dict with 'candidates', 'pdf_sha256', 'meta'.
        Enables seamless integration with Streamlit and automated pipelines.
        """
        sentences, meta = self.parse_pdf(pdf_path, tender_id)
        if use_llm_assist:
            sentences = self.refine_segmentation_with_llm(sentences)
            meta["total_candidates"] = len(sentences)
        return {
            "candidates": sentences,
            "pdf_sha256": meta["pdf_sha256"],
            "meta": meta
        }

    def refine_segmentation_with_llm(
        self,
        sentences: List[Dict[str, Any]],
        extractor: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """
        LLM Parser Assistant (Nemotron-Powered Segmentation Safeguard):
        Inspects complex or long sentences (>250 chars or containing multiple semicolons/clauses)
        where standard deterministic splitting might have merged multiple distinct requirements.
        Splits them into deterministic sub-IDs (_s001a, _s001b) ensuring NO requirement is swallowed.
        """
        if extractor is None:
            try:
                from src.extractors.llm_extractor import LLMExtractor
                extractor = LLMExtractor()
            except Exception:
                return sentences

        refined = []
        for s in sentences:
            text = s["text"]
            # Trigger LLM segmentation only for long, complex sentences with multiple clauses
            if len(text) > 250 and (";" in text or " and " in text or ":" in text):
                prompt = (
                    "Split the following government RFP text into distinct, standalone contractual clauses or requirements. "
                    "If it is already a single requirement, return a list with just that one string. "
                    "Return a JSON object: {\"clauses\": [\"clause 1\", \"clause 2\"]}\n\n"
                    f"TEXT: {text}"
                )
                try:
                    resp = extractor.client.chat.completions.create(
                        model=extractor.model,
                        messages=[{"role": "user", "content": prompt}],
                        response_format={"type": "json_object"},
                        max_tokens=600,
                        temperature=0.0
                    )
                    content = resp.choices[0].message.content or "{}"
                    data = json.loads(content)
                    clauses = data.get("clauses", [text])
                    if len(clauses) > 1:
                        suffixes = "abcdefghijklmnopqrstuvwxyz"
                        for idx, c in enumerate(clauses):
                            s_copy = dict(s)
                            sub_suffix = suffixes[idx] if idx < len(suffixes) else f"_{idx}"
                            s_copy["sentence_id"] = f"{s['sentence_id']}{sub_suffix}"
                            s_copy["text"] = c.strip()
                            refined.append(s_copy)
                        continue
                except Exception as e:
                    print(f"LLM segmentation fallback: {e}")
            refined.append(s)
        return refined
