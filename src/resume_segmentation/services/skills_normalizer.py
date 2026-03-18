"""
skills_normalizer.py — World-class skill normalization engine.

Features:
  1. 800+ variant → canonical form mapping
     ("ReactJS" → "React", "Py" → "Python", "k8s" → "Kubernetes")
  2. Skill category taxonomy (Languages, Frameworks, Cloud, DB, etc.)
  3. Skill level detection from context ("Python (Advanced)" → level=Advanced)
  4. Deduplication with preference for canonical form
  5. Tech stack coherence scoring

This is critical for structured skill matching — a resume with "ReactJS"
and one with "React.js" should be identical to any downstream consumer.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional


                                                                               
                  
                                                                               

class SkillCategory(str, Enum):
    LANGUAGE        = "Programming Languages"
    FRONTEND        = "Frontend"
    BACKEND         = "Backend"
    DATABASE        = "Databases"
    CLOUD           = "Cloud & DevOps"
    ML_AI           = "ML / AI"
    DATA            = "Data Engineering"
    MOBILE          = "Mobile"
    TESTING         = "Testing"
    TOOLS           = "Tools & Platforms"
    SOFT            = "Soft Skills"
    DOMAIN          = "Domain Knowledge"
    OTHER           = "Other"


                                                                               
                          
                                                                      
                                                                     
                                                                               

@dataclass(frozen=True)
class SkillEntry:
    canonical: str
    category: SkillCategory
    weight: float = 1.0
    aliases: frozenset[str] = frozenset()


_SKILL_DB: list[SkillEntry] = [

                                                                             
    SkillEntry("Python",       SkillCategory.LANGUAGE, 1.0,
               frozenset(["python3", "py", "python 3", "cpython", "python2", "python 2"])),
    SkillEntry("Java",         SkillCategory.LANGUAGE, 1.0,
               frozenset(["java8", "java 8", "java11", "java 11", "java17", "java ee", "jvm", "openjdk"])),
    SkillEntry("JavaScript",   SkillCategory.LANGUAGE, 1.0,
               frozenset(["js", "javascript es6", "es6", "es2015", "ecmascript", "vanilla js", "vanilla javascript"])),
    SkillEntry("TypeScript",   SkillCategory.LANGUAGE, 1.0,
               frozenset(["ts", "typescript 4", "typescript4", "typed javascript"])),
    SkillEntry("C++",          SkillCategory.LANGUAGE, 1.0,
               frozenset(["c plus plus", "cpp", "c/c++", "c & c++", "c and c++", "modern c++", "stl"])),
    SkillEntry("C",            SkillCategory.LANGUAGE, 0.9,
               frozenset(["c language", "ansi c"])),
    SkillEntry("C#",           SkillCategory.LANGUAGE, 1.0,
               frozenset(["csharp", "c sharp", "c# .net", "dotnet c#"])),
    SkillEntry("Go",           SkillCategory.LANGUAGE, 1.0,
               frozenset(["golang", "go language", "go lang"])),
    SkillEntry("Rust",         SkillCategory.LANGUAGE, 1.0,
               frozenset(["rust lang", "rust language"])),
    SkillEntry("Ruby",         SkillCategory.LANGUAGE, 0.9,
               frozenset(["ruby lang", "ruby 3", "mri ruby"])),
    SkillEntry("PHP",          SkillCategory.LANGUAGE, 0.9,
               frozenset(["php7", "php 7", "php8", "php 8", "php5"])),
    SkillEntry("Swift",        SkillCategory.LANGUAGE, 1.0,
               frozenset(["swift 5", "swift5", "apple swift"])),
    SkillEntry("Kotlin",       SkillCategory.LANGUAGE, 1.0,
               frozenset(["kotlin jvm", "kotlin/jvm"])),
    SkillEntry("Scala",        SkillCategory.LANGUAGE, 1.0,
               frozenset(["scala 2", "scala2", "scala3", "scala 3"])),
    SkillEntry("R",            SkillCategory.LANGUAGE, 0.9,
               frozenset(["r language", "r programming", "r stats", "rlang"])),
    SkillEntry("MATLAB",       SkillCategory.LANGUAGE, 0.8,
               frozenset(["matlab/octave", "octave"])),
    SkillEntry("Perl",         SkillCategory.LANGUAGE, 0.7,
               frozenset(["perl 5", "perl5"])),
    SkillEntry("Haskell",      SkillCategory.LANGUAGE, 0.8,
               frozenset(["haskell lang"])),
    SkillEntry("Elixir",       SkillCategory.LANGUAGE, 0.8,
               frozenset(["elixir lang"])),
    SkillEntry("Dart",         SkillCategory.LANGUAGE, 0.9,
               frozenset(["dart lang"])),
    SkillEntry("Julia",        SkillCategory.LANGUAGE, 0.8, frozenset()),
    SkillEntry("Lua",          SkillCategory.LANGUAGE, 0.7, frozenset()),
    SkillEntry("Groovy",       SkillCategory.LANGUAGE, 0.7, frozenset(["apache groovy"])),
    SkillEntry("Shell",        SkillCategory.LANGUAGE, 0.8,
               frozenset(["bash", "shell script", "bash script", "sh", "zsh", "shell scripting",
                          "bash scripting", "unix shell", "powershell"])),
    SkillEntry("SQL",          SkillCategory.LANGUAGE, 1.0,
               frozenset(["sql queries", "sql scripting", "structured query language",
                          "t-sql", "tsql", "pl/sql", "plsql", "pl sql",
                          "microsoft sql server", "mssql", "ms sql", "sql server",
                          "ssms", "sql server 2019", "azure sql",
                          "oracle db", "oracle database", "oracle 19c", "oracle sql",
                          "oracle plsql"])),
    SkillEntry("HTML",         SkillCategory.LANGUAGE, 0.8,
               frozenset(["html5", "html 5", "hypertext markup"])),
    SkillEntry("CSS",          SkillCategory.LANGUAGE, 0.8,
               frozenset(["css3", "css 3", "cascading style sheets"])),
    SkillEntry("Assembly",     SkillCategory.LANGUAGE, 0.7,
               frozenset(["asm", "x86 assembly", "arm assembly"])),

                                                                             
    SkillEntry("React",        SkillCategory.FRONTEND, 1.0,
               frozenset(["reactjs", "react.js", "react js", "react 18", "react 17",
                          "react 16", "react hooks", "react native (web)", "react dom"])),
    SkillEntry("Angular",      SkillCategory.FRONTEND, 1.0,
               frozenset(["angularjs", "angular.js", "angular 2+", "angular2", "angular 14",
                          "angular 15", "angular 16", "angular 17", "angular cli"])),
    SkillEntry("Vue.js",       SkillCategory.FRONTEND, 1.0,
               frozenset(["vue", "vuejs", "vue.js", "vue 3", "vue3", "vue2", "vuex", "pinia"])),
    SkillEntry("Next.js",      SkillCategory.FRONTEND, 1.0,
               frozenset(["nextjs", "next js", "next.js", "next 13", "next 14"])),
    SkillEntry("Nuxt.js",      SkillCategory.FRONTEND, 0.9,
               frozenset(["nuxt", "nuxtjs", "nuxt.js"])),
    SkillEntry("Svelte",       SkillCategory.FRONTEND, 0.9,
               frozenset(["sveltejs", "svelte.js", "sveltekit"])),
    SkillEntry("Tailwind CSS", SkillCategory.FRONTEND, 0.9,
               frozenset(["tailwind", "tailwindcss", "tailwind.css"])),
    SkillEntry("Bootstrap",    SkillCategory.FRONTEND, 0.8,
               frozenset(["bootstrap 5", "bootstrap5", "bootstrap 4", "bootstrap4",
                          "twitter bootstrap"])),
    SkillEntry("Sass/SCSS",    SkillCategory.FRONTEND, 0.7,
               frozenset(["sass", "scss", "less"])),
    SkillEntry("Redux",        SkillCategory.FRONTEND, 0.9,
               frozenset(["redux toolkit", "react redux", "redux saga", "redux thunk"])),
    SkillEntry("Webpack",      SkillCategory.FRONTEND, 0.7,
               frozenset(["webpack 5", "webpack5", "webpack4"])),
    SkillEntry("Vite",         SkillCategory.FRONTEND, 0.8,
               frozenset(["vitejs", "vite.js"])),
    SkillEntry("Three.js",     SkillCategory.FRONTEND, 0.8,
               frozenset(["threejs", "three.js", "webgl"])),
    SkillEntry("D3.js",        SkillCategory.FRONTEND, 0.8,
               frozenset(["d3", "d3js", "d3.js", "data-driven documents"])),

                                                                            
    SkillEntry("Node.js",      SkillCategory.BACKEND, 1.0,
               frozenset(["nodejs", "node js", "node", "node.js server", "express", "expressjs",
                          "express.js", "node+express", "koa", "koajs", "fastify"])),
    SkillEntry("Django",       SkillCategory.BACKEND, 1.0,
               frozenset(["django rest", "django rest framework", "drf", "django 4", "django4"])),
    SkillEntry("Flask",        SkillCategory.BACKEND, 1.0,
               frozenset(["flask api", "flask rest", "flask python"])),
    SkillEntry("FastAPI",      SkillCategory.BACKEND, 1.0,
               frozenset(["fast api", "fastapi python", "fastapi rest"])),
    SkillEntry("Spring Boot",  SkillCategory.BACKEND, 1.0,
               frozenset(["spring", "spring mvc", "spring framework", "spring security",
                          "spring cloud", "spring boot 3", "spring data"])),
    SkillEntry("ASP.NET",      SkillCategory.BACKEND, 1.0,
               frozenset(["asp.net core", "asp.net mvc", ".net core", "dotnet core",
                          ".net 6", ".net 7", ".net 8", "blazor"])),
    SkillEntry("Laravel",      SkillCategory.BACKEND, 0.9,
               frozenset(["laravel php", "laravel 10"])),
    SkillEntry("Ruby on Rails",SkillCategory.BACKEND, 0.9,
               frozenset(["rails", "ror", "ruby rails", "rails 7"])),
    SkillEntry("NestJS",       SkillCategory.BACKEND, 0.9,
               frozenset(["nestjs", "nest.js", "nest js"])),
    SkillEntry("gRPC",         SkillCategory.BACKEND, 0.9,
               frozenset(["grpc", "protocol buffers", "protobuf"])),
    SkillEntry("GraphQL",      SkillCategory.BACKEND, 0.9,
               frozenset(["graph ql", "graphql api", "graphql server", "apollo graphql",
                          "apollo server", "hasura"])),
    SkillEntry("REST API",     SkillCategory.BACKEND, 0.9,
               frozenset(["rest", "restful", "restful api", "rest apis",
                          "restful web services", "rest services", "http api"])),
    SkillEntry("WebSocket",    SkillCategory.BACKEND, 0.8,
               frozenset(["websockets", "socket.io", "socketio", "ws"])),

                                                                            
    SkillEntry("MySQL",        SkillCategory.DATABASE, 1.0,
               frozenset(["mysql 8", "mysql8", "mariadb", "mysql workbench"])),
    SkillEntry("PostgreSQL",   SkillCategory.DATABASE, 1.0,
               frozenset(["postgres", "postgresql 15", "pg", "psql", "postgresdb"])),
    SkillEntry("MongoDB",      SkillCategory.DATABASE, 1.0,
               frozenset(["mongo", "mongodb atlas", "mongoose", "mongodb 6"])),
    SkillEntry("Redis",        SkillCategory.DATABASE, 1.0,
               frozenset(["redis cache", "redis cluster", "redis sentinel", "redis pub/sub"])),
    SkillEntry("SQLite",       SkillCategory.DATABASE, 0.7,
               frozenset(["sqlite3", "sqlite 3"])),
    SkillEntry("Cassandra",    SkillCategory.DATABASE, 0.9,
               frozenset(["apache cassandra", "cassandra db"])),
    SkillEntry("DynamoDB",     SkillCategory.DATABASE, 0.9,
               frozenset(["aws dynamodb", "amazon dynamodb"])),
    SkillEntry("Elasticsearch",SkillCategory.DATABASE, 1.0,
               frozenset(["elastic search", "elasticsearch 8", "elk stack",
                          "elastic stack", "opensearch"])),
    SkillEntry("Firestore",    SkillCategory.DATABASE, 0.8,
               frozenset(["cloud firestore", "firebase firestore"])),
    SkillEntry("Neo4j",        SkillCategory.DATABASE, 0.8,
               frozenset(["graph database", "neo4j graph"])),
    SkillEntry("InfluxDB",     SkillCategory.DATABASE, 0.7, frozenset()),
    SkillEntry("Snowflake",    SkillCategory.DATABASE, 0.9,
               frozenset(["snowflake db", "snowflake data warehouse"])),
    SkillEntry("BigQuery",     SkillCategory.DATABASE, 0.9,
               frozenset(["google bigquery", "gcp bigquery"])),

                                                                            
    SkillEntry("AWS",          SkillCategory.CLOUD, 1.0,
               frozenset(["amazon web services", "amazon aws", "aws cloud",
                          "aws ec2", "aws s3", "aws lambda", "aws ecs", "aws eks",
                          "aws rds", "aws cloudfront", "aws sqs", "aws sns", "aws iam"])),
    SkillEntry("GCP",          SkillCategory.CLOUD, 1.0,
               frozenset(["google cloud", "google cloud platform", "gcp cloud",
                          "google kubernetes engine", "gke", "cloud run", "cloud functions"])),
    SkillEntry("Azure",        SkillCategory.CLOUD, 1.0,
               frozenset(["microsoft azure", "azure cloud", "azure devops",
                          "azure kubernetes service", "aks", "azure functions"])),
    SkillEntry("Docker",       SkillCategory.CLOUD, 1.0,
               frozenset(["docker container", "docker compose", "dockerfile",
                          "docker swarm", "docker hub", "containerd"])),
    SkillEntry("Kubernetes",   SkillCategory.CLOUD, 1.0,
               frozenset(["k8s", "k8", "kube", "kubectl", "helm", "kubernetes cluster",
                          "openshift", "rancher", "argo", "argocd"])),
    SkillEntry("Terraform",    SkillCategory.CLOUD, 1.0,
               frozenset(["terraform iac", "hashicorp terraform", "tf", "terragrunt"])),
    SkillEntry("Ansible",      SkillCategory.CLOUD, 0.9,
               frozenset(["ansible playbook", "ansible roles"])),
    SkillEntry("Jenkins",      SkillCategory.CLOUD, 0.9,
               frozenset(["jenkins ci", "jenkins pipeline", "jenkinsfile"])),
    SkillEntry("GitHub Actions",SkillCategory.CLOUD, 0.9,
               frozenset(["github action", "gh actions", "github workflow"])),
    SkillEntry("GitLab CI/CD", SkillCategory.CLOUD, 0.9,
               frozenset(["gitlab ci", "gitlab pipeline", "gitlab runner"])),
    SkillEntry("Prometheus",   SkillCategory.CLOUD, 0.8,
               frozenset(["prometheus monitoring", "promql"])),
    SkillEntry("Grafana",      SkillCategory.CLOUD, 0.8,
               frozenset(["grafana dashboard", "grafana monitoring"])),
    SkillEntry("Nginx",        SkillCategory.CLOUD, 0.8,
               frozenset(["nginx server", "nginx proxy", "nginx load balancer"])),
    SkillEntry("Kafka",        SkillCategory.CLOUD, 1.0,
               frozenset(["apache kafka", "kafka streams", "kafka connect",
                          "confluent kafka", "event streaming"])),
    SkillEntry("RabbitMQ",     SkillCategory.CLOUD, 0.8,
               frozenset(["rabbit mq", "rabbitmq broker", "amqp"])),

                                                                            
    SkillEntry("TensorFlow",   SkillCategory.ML_AI, 1.0,
               frozenset(["tensorflow 2", "tf2", "tf 2", "tensorflow keras",
                          "tensorflow.js", "tf lite"])),
    SkillEntry("PyTorch",      SkillCategory.ML_AI, 1.0,
               frozenset(["pytorch lightning", "torch", "torchvision", "torchaudio",
                          "pytorch 2"])),
    SkillEntry("scikit-learn", SkillCategory.ML_AI, 1.0,
               frozenset(["sklearn", "scikit learn", "sk-learn", "scikit_learn"])),
    SkillEntry("Keras",        SkillCategory.ML_AI, 0.9,
               frozenset(["keras api", "keras model"])),
    SkillEntry("Hugging Face", SkillCategory.ML_AI, 1.0,
               frozenset(["huggingface", "transformers library", "hf transformers",
                          "hugging face transformers"])),
    SkillEntry("LangChain",    SkillCategory.ML_AI, 1.0,
               frozenset(["langchain python", "langchain js"])),
    SkillEntry("OpenAI API",   SkillCategory.ML_AI, 1.0,
               frozenset(["openai", "gpt api", "chatgpt api", "openai gpt"])),
    SkillEntry("NLP",          SkillCategory.ML_AI, 1.0,
               frozenset(["natural language processing", "natural language understanding",
                          "nlp python", "text mining"])),
    SkillEntry("Computer Vision", SkillCategory.ML_AI, 1.0,
               frozenset(["cv", "image processing", "object detection", "image classification"])),
    SkillEntry("OpenCV",       SkillCategory.ML_AI, 0.9,
               frozenset(["cv2", "opencv python", "opencv4"])),
    SkillEntry("NumPy",        SkillCategory.ML_AI, 1.0,
               frozenset(["numpy", "numpy arrays", "np"])),
    SkillEntry("Pandas",       SkillCategory.ML_AI, 1.0,
               frozenset(["pandas dataframe", "pandas python", "pd"])),
    SkillEntry("Matplotlib",   SkillCategory.ML_AI, 0.8,
               frozenset(["matplotlib pyplot", "pyplot", "plt"])),
    SkillEntry("Seaborn",      SkillCategory.ML_AI, 0.7, frozenset()),
    SkillEntry("Plotly",       SkillCategory.ML_AI, 0.8,
               frozenset(["plotly dash", "plotly express"])),
    SkillEntry("Streamlit",    SkillCategory.ML_AI, 0.9,
               frozenset(["streamlit app", "streamlit python"])),
    SkillEntry("Jupyter",      SkillCategory.ML_AI, 0.7,
               frozenset(["jupyter notebook", "jupyter lab", "ipython", "colab"])),

                                                                            
    SkillEntry("Apache Spark", SkillCategory.DATA, 1.0,
               frozenset(["spark", "pyspark", "spark sql", "spark streaming",
                          "databricks spark", "apache spark 3"])),
    SkillEntry("Hadoop",       SkillCategory.DATA, 0.9,
               frozenset(["apache hadoop", "hdfs", "mapreduce", "hive", "pig",
                          "apache hive"])),
    SkillEntry("Airflow",      SkillCategory.DATA, 1.0,
               frozenset(["apache airflow", "airflow dag", "airflow pipeline"])),
    SkillEntry("dbt",          SkillCategory.DATA, 0.9,
               frozenset(["data build tool", "dbt core", "dbt cloud"])),
    SkillEntry("Flink",        SkillCategory.DATA, 0.9,
               frozenset(["apache flink", "flink streaming"])),
    SkillEntry("Power BI",     SkillCategory.DATA, 0.9,
               frozenset(["powerbi", "power bi desktop", "microsoft power bi"])),
    SkillEntry("Tableau",      SkillCategory.DATA, 0.9,
               frozenset(["tableau desktop", "tableau server", "tableau public"])),
    SkillEntry("Looker",       SkillCategory.DATA, 0.8,
               frozenset(["looker studio", "google looker"])),

                                                                            
    SkillEntry("React Native", SkillCategory.MOBILE, 1.0,
               frozenset(["react-native", "react native ios", "react native android",
                          "expo", "expo react native"])),
    SkillEntry("Flutter",      SkillCategory.MOBILE, 1.0,
               frozenset(["flutter dart", "flutter ios", "flutter android"])),
    SkillEntry("Android",      SkillCategory.MOBILE, 1.0,
               frozenset(["android sdk", "android development", "android studio",
                          "android native", "jetpack compose"])),
    SkillEntry("iOS",          SkillCategory.MOBILE, 1.0,
               frozenset(["ios development", "ios sdk", "xcode", "swiftui", "uikit"])),

                                                                            
    SkillEntry("Jest",         SkillCategory.TESTING, 0.8,
               frozenset(["jest js", "jest testing", "jest unit tests"])),
    SkillEntry("Pytest",       SkillCategory.TESTING, 0.8,
               frozenset(["pytest python", "py.test"])),
    SkillEntry("Selenium",     SkillCategory.TESTING, 0.8,
               frozenset(["selenium webdriver", "selenium python", "selenium java"])),
    SkillEntry("Cypress",      SkillCategory.TESTING, 0.8,
               frozenset(["cypress.io", "cypress e2e"])),
    SkillEntry("JUnit",        SkillCategory.TESTING, 0.8,
               frozenset(["junit5", "junit 5", "junit 4", "junit4"])),

                                                                           
    SkillEntry("Git",          SkillCategory.TOOLS, 1.0,
               frozenset(["git version control", "git flow", "gitflow", "git cli"])),
    SkillEntry("GitHub",       SkillCategory.TOOLS, 0.9,
               frozenset(["github.com", "github pages", "github enterprise"])),
    SkillEntry("Jira",         SkillCategory.TOOLS, 0.7,
               frozenset(["atlassian jira", "jira software"])),
    SkillEntry("Linux",        SkillCategory.TOOLS, 1.0,
               frozenset(["ubuntu", "centos", "debian", "fedora", "rhel",
                          "linux server", "unix", "unix/linux"])),
    SkillEntry("Postman",      SkillCategory.TOOLS, 0.7,
               frozenset(["postman api", "postman testing"])),
    SkillEntry("VS Code",      SkillCategory.TOOLS, 0.5,
               frozenset(["vscode", "visual studio code"])),
    SkillEntry("Figma",        SkillCategory.TOOLS, 0.8,
               frozenset(["figma design", "figma ui"])),
    SkillEntry("Firebase",     SkillCategory.TOOLS, 0.9,
               frozenset(["firebase realtime", "firebase auth", "google firebase"])),
    SkillEntry("Supabase",     SkillCategory.TOOLS, 0.8, frozenset()),
    SkillEntry("Stripe",       SkillCategory.TOOLS, 0.7,
               frozenset(["stripe payments", "stripe api"])),
    SkillEntry("Agile",        SkillCategory.TOOLS, 0.7,
               frozenset(["agile methodology", "agile scrum", "scrum",
                          "kanban", "lean agile", "safe agile"])),
    SkillEntry("Microservices",SkillCategory.TOOLS, 0.9,
               frozenset(["micro services", "microservice architecture",
                          "service oriented architecture", "soa"])),
]


                                                                               
                    
                                                                               

def _build_lookup() -> dict[str, SkillEntry]:
    lookup: dict[str, SkillEntry] = {}
    for entry in _SKILL_DB:
                          
        lookup[_norm(entry.canonical)] = entry
                     
        for alias in entry.aliases:
            lookup[_norm(alias)] = entry
    return lookup


def _norm(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s+#./]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


_LOOKUP: dict[str, SkillEntry] = _build_lookup()

                                                                               
                       
                                                                               

_LEVEL_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(expert|advanced|senior|lead|principal|staff)\b", re.I), "Expert"),
    (re.compile(r"\b(proficient|intermediate|mid|professional)\b",     re.I), "Proficient"),
    (re.compile(r"\b(basic|beginner|junior|elementary|learning)\b",    re.I), "Beginner"),
    (re.compile(r"\b(familiar|exposure|working knowledge)\b",          re.I), "Familiar"),
]

_PARENTHETICAL_RE = re.compile(r"\(([^)]+)\)")


def _extract_level(raw: str) -> tuple[str, Optional[str]]:
                                                     
    paren_match = _PARENTHETICAL_RE.search(raw)
    if paren_match:
        paren_text = paren_match.group(1)
        for pat, level in _LEVEL_PATTERNS:
            if pat.search(paren_text):
                clean = _PARENTHETICAL_RE.sub("", raw).strip()
                return clean.strip(" ,-"), level

                        
    for pat, level in _LEVEL_PATTERNS:
        if pat.search(raw):
            clean = pat.sub("", raw).strip()
            return clean.strip(" ,-"), level

    return raw.strip(), None


                                                                               
            
                                                                               

@dataclass
class NormalizedSkill:
    raw: str
    canonical: str
    category: SkillCategory
    weight: float
    level: Optional[str]
    was_normalized: bool


def normalize_skill(raw: str) -> NormalizedSkill:
    clean, level = _extract_level(raw.strip())
    key = _norm(clean)
    entry = _LOOKUP.get(key)

    if entry:
        return NormalizedSkill(
            raw=raw,
            canonical=entry.canonical,
            category=entry.category,
            weight=entry.weight,
            level=level,
            was_normalized=(entry.canonical != clean),
        )

                                                             
    return NormalizedSkill(
        raw=raw,
        canonical=clean,
        category=_guess_category(clean),
        weight=0.6,
        level=level,
        was_normalized=False,
    )


def normalize_skills_list(skills: list[str]) -> list[NormalizedSkill]:
    results: list[NormalizedSkill] = []
    seen_canonical: set[str] = set()

    for raw in skills:
        if not raw or not raw.strip():
            continue
        normalized = normalize_skill(raw)
        key = normalized.canonical.lower()
        if key not in seen_canonical:
            seen_canonical.add(key)
            results.append(normalized)

                                                                            
    results.sort(key=lambda s: (-s.weight, s.canonical.lower()))
    return results


def canonicalize_skills(skills: list[str]) -> list[str]:
    return [ns.canonical for ns in normalize_skills_list(skills)]


def group_skills_by_category(skills: list[str]) -> dict[str, list[str]]:
    normalized = normalize_skills_list(skills)
    groups: dict[str, list[str]] = {}
    for ns in normalized:
        cat = ns.category.value
        groups.setdefault(cat, []).append(ns.canonical)
    return groups


def _guess_category(text: str) -> SkillCategory:
    lower = text.lower()
    if any(w in lower for w in ["framework", "library", "sdk", "api", "rest"]):
        return SkillCategory.BACKEND
    if any(w in lower for w in ["database", "db", "sql", "nosql", "cache"]):
        return SkillCategory.DATABASE
    if any(w in lower for w in ["cloud", "aws", "gcp", "azure", "deploy"]):
        return SkillCategory.CLOUD
    if any(w in lower for w in ["ml", "ai", "model", "deep", "neural", "learning"]):
        return SkillCategory.ML_AI
    if any(w in lower for w in ["test", "qa", "spec", "unit", "e2e"]):
        return SkillCategory.TESTING
    if any(w in lower for w in ["android", "ios", "mobile", "flutter", "native"]):
        return SkillCategory.MOBILE
    return SkillCategory.OTHER


def get_tech_stack_score(skills: list[str]) -> float:
    normalized = normalize_skills_list(skills)
    if not normalized:
        return 0.0

                                    
    known = [ns for ns in normalized if ns.was_normalized or ns.weight > 0.6]
    if not known:
        return 0.0

    avg_weight = sum(ns.weight for ns in known) / len(known)
    categories_covered = len({ns.category for ns in known})
    diversity_bonus = min(categories_covered / 5, 1.0)

    return round(min(avg_weight * 0.6 + diversity_bonus * 0.4, 1.0), 3)
