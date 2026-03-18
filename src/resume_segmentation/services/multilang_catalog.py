"""
multilang_catalog.py — Multi-language resume section heading catalog.

Supports section headings in:
  Hindi (Devanagari + Romanized)
  Spanish
  French
  German
  Portuguese
  Arabic (Romanized)
  Chinese (Simplified, Romanized Pinyin)
  Japanese (Romanized)

Integrated transparently into section_catalog.py's match_section_heading().
"""
from __future__ import annotations

import re
import unicodedata

                                                                               
                      
                                                         
                                                                               

_MULTILANG: dict[str, str] = {

                                                                             
    "anubhav":           "experience",
    "kaam ka anubhav":   "experience",
    "karya anubhav":     "experience",
    "vyavsayik anubhav": "experience",
    "shiksha":           "education",
    "shaikshanik yogyata": "education",
    "shaikshanik parishthiti": "education",
    "yogyata":           "education",
    "kaushal":           "skills",
    "takniki kaushal":   "skills",
    "prafikyta":         "skills",
    "prarambh":          "summary",
    "parichay":          "summary",
    "vyaktigat parichay": "summary",
    "uddeshy":           "summary",
    "lakshy":            "summary",
    "pariyojana":        "projects",
    "pariyojanayen":     "projects",
    "uplabdhiyan":       "awards",
    "puraskar":          "awards",
    "samman":            "awards",
    "ruchi":             "interests",
    "abhiruchi":         "interests",
    "shoq":              "interests",
    "bhasha":            "languages",
    "bhashayen":         "languages",
    "prmaanpatra":       "certifications",
    "pramaanpatra":      "certifications",
    "sandarbh":          "references",

                                                                             
    "अनुभव":             "experience",
    "कार्य अनुभव":       "experience",
    "शिक्षा":            "education",
    "योग्यता":           "education",
    "कौशल":              "skills",
    "तकनीकी कौशल":       "skills",
    "परिचय":             "summary",
    "उद्देश्य":          "summary",
    "परियोजना":          "projects",
    "परियोजनाएं":        "projects",
    "पुरस्कार":          "awards",
    "उपलब्धियां":        "awards",
    "रुचि":              "interests",
    "भाषा":              "languages",
    "प्रमाणपत्र":        "certifications",

                                                                             
    "experiencia":                "experience",
    "experiencia laboral":        "experience",
    "experiencia profesional":    "experience",
    "historial laboral":          "experience",
    "historial profesional":      "experience",
    "educacion":                  "education",
    "educación":                  "education",
    "formacion academica":        "education",
    "formación académica":        "education",
    "estudios":                   "education",
    "habilidades":                "skills",
    "habilidades tecnicas":       "skills",
    "habilidades técnicas":       "skills",
    "competencias":               "skills",
    "competencias tecnicas":      "skills",
    "destrezas":                  "skills",
    "perfil":                     "summary",
    "resumen profesional":        "summary",
    "objetivo profesional":       "summary",
    "presentacion":               "summary",
    "proyectos":                  "projects",
    "logros":                     "awards",
    "premios":                    "awards",
    "reconocimientos":            "awards",
    "intereses":                  "interests",
    "hobbies":                    "interests",
    "aficiones":                  "interests",
    "idiomas":                    "languages",
    "certificaciones":            "certifications",
    "cursos":                     "courses",
    "referencias":                "references",
    "voluntariado":               "volunteer",
    "publicaciones":              "publications",

                                                                            
    "experience":                 "experience",
    "expérience":                 "experience",
    "experience professionnelle": "experience",
    "expérience professionnelle": "experience",
    "parcours professionnel":     "experience",
    "formation":                  "education",
    "education":                  "education",
    "diplomes":                   "education",
    "diplômes":                   "education",
    "competences":                "skills",
    "compétences":                "skills",
    "competences techniques":     "skills",
    "compétences techniques":     "skills",    "profil":                     "summary",
    "resume":                     "summary",
    "résumé":                     "summary",
    "objectif":                   "summary",
    "projets":                    "projects",
    "realisations":               "awards",
    "réalisations":               "awards",
    "distinctions":               "awards",
    "centres d interet":          "interests",
    "centres d'intérêt":          "interests",
    "loisirs":                    "interests",
    "langues":                    "languages",
    "certifications":             "certifications",
    "references":                 "references",
    "benevole":                   "volunteer",
    "bénévolat":                  "volunteer",
    "publications":               "publications",

                                                                            
    "berufserfahrung":            "experience",
    "arbeitserfahrung":           "experience",
    "beruflicher werdegang":      "experience",
    "ausbildung":                 "education",
    "bildung":                    "education",
    "studium":                    "education",
    "kenntnisse":                 "skills",
    "fahigkeiten":                "skills",
    "fähigkeiten":                "skills",
    "technische kenntnisse":      "skills",
    "profil":                     "summary",
    "kurzprofil":                 "summary",
    "berufsziel":                 "summary",
    "projekte":                   "projects",
    "auszeichnungen":             "awards",
    "errungenschaften":           "awards",
    "hobbys":                     "interests",
    "interessen":                 "interests",
    "freizeitaktivitaten":        "interests",
    "sprachen":                   "languages",
    "zertifikate":                "certifications",
    "referenzen":                 "references",
    "ehrenamt":                   "volunteer",
    "freiwilligenarbeit":         "volunteer",
    "veroffentlichungen":         "publications",
    "veröffentlichungen":         "publications",

                                                                           
    "experiencia profissional":   "experience",
    "experiência profissional":   "experience",
    "historico profissional":     "experience",
    "educacao":                   "education",
    "educação":                   "education",
    "formacao":                   "education",
    "formação":                   "education",
    "habilidades":                "skills",
    "competencias":               "skills",
    "competências":               "skills",
    "perfil profissional":        "summary",
    "objetivo":                   "summary",
    "projetos":                   "projects",
    "conquistas":                 "awards",
    "premios":                    "awards",
    "interesses":                 "interests",
    "passatempos":                "interests",
    "idiomas":                    "languages",
    "certificacoes":              "certifications",
    "certificações":              "certifications",
    "referencias":                "references",
    "voluntariado":               "volunteer",
    "publicacoes":                "publications",
    "publicações":                "publications",

                                                                            
    "khibra":                     "experience",
    "khebra":                     "experience",
    "khibrat al amal":            "experience",
    "al khibra":                  "experience",
    "taleem":                     "education",
    "taeleem":                    "education",
    "al taleem":                  "education",
    "maharat":                    "skills",
    "almaharat":                  "skills",
    "nubtha":                     "summary",
    "masharie":                   "projects",
    "masharee":                   "projects",
    "ingzat":                     "awards",
    "jawaez":                     "awards",
    "al jawaez":                  "awards",
    "lughat":                     "languages",
    "al lughat":                  "languages",
    "shahadat":                   "certifications",

                                                                            
    "gongzuo jingyan":            "experience",
    "gong zuo jing yan":          "experience",
    "jiaoyu jingli":              "education",
    "jiao yu":                    "education",
    "jinneng":                    "skills",
    "ji neng":                    "skills",
    "zhuanye jinneng":            "skills",
    "gerenjianjie":               "summary",
    "ge ren jian jie":            "summary",
    "xiangmu":                    "projects",
    "xiang mu":                   "projects",
    "rong yu":                    "awards",
    "huojiang":                   "awards",
    "xingqu aihao":               "interests",
    "yuyan nengli":               "languages",
    "zhengshu":                   "certifications",

                                                                           
    "shokureki":                  "experience",
    "kyoiku":                     "education",
    "gakureki":                   "education",
    "sukiru":                     "skills",
    "jiko pr":                    "summary",
    "purojekuto":                 "projects",
    "shikaku":                    "certifications",
    "keireki gaiyou":             "summary",
    "kyoumi":                     "interests",
    "gengoryoku":                 "languages",
}


                                                                               
               
                                                                               

def _normalize_multilang(text: str) -> str:
    result: list[str] = []
    nfkd = unicodedata.normalize("NFKD", text)
    for ch in nfkd:
                                                                                     
                                                                                 
        if unicodedata.category(ch) == "Mn":
            cp = ord(ch)
            if 0x0300 <= cp <= 0x036F:                                   
                continue
        result.append(ch)
    text = "".join(result)
    text = text.lower()
                                                                     
    text = re.sub(
        r"[^\w\s\u0900-\u097f\u0600-\u06ff\u4e00-\u9fff\u3040-\u30ff]",
        " ", text
    )
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def match_multilang_heading(text: str) -> str | None:
    if not text:
        return None

    normalized = _normalize_multilang(text.strip())
    if not normalized:
        return None

                       
    result = _MULTILANG.get(normalized)
    if result:
        return result

                                                 
    stripped = re.sub(r"[\s:.\-–—/|]+$", "", normalized)
    if stripped != normalized:
        result = _MULTILANG.get(stripped)
        if result:
            return result

    return None


def get_supported_languages() -> list[str]:
    return [
        "Hindi (Devanagari + Romanized)",
        "Spanish",
        "French",
        "German",
        "Portuguese",
        "Arabic (Romanized)",
        "Chinese Simplified (Pinyin)",
        "Japanese (Romanized)",
    ]
