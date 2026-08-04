import "./Landing.css";
import { Link } from "react-router-dom";

function Landing() {
    return (
        <div className="landing">

            {/* ================= NAVBAR ================= */}

            <nav className="navbar">
                <div className="logo">
                    <span>🎓</span>
                    <h2>EduMind AI</h2>
                </div>

                <div className="nav-links">
                    <a href="#features">Features</a>
                    <a href="#how">How It Works</a>
                    <a href="#technology">Technology</a>
                    <a href="#faq">FAQ</a>
                </div>

                <div className="nav-buttons">
                    <Link to="/login" className="login-btn">
                        Login
                    </Link>

                    <Link to="/signup" className="signup-btn">
                        Get Started
                    </Link>
                </div>
            </nav>

            {/* ================= HERO ================= */}

            <section className="hero">

                <div className="hero-left">

                    <span className="badge">
                        AI Powered Adaptive Learning
                    </span>

                    <h1>
                        Learn Smarter with
                        <span> EduMind AI</span>
                    </h1>

                    <p>
                        EduMind is an AI-powered adaptive tutoring platform
                        that personalizes explanations according to each
                        student's learning level. It answers questions from
                        uploaded study material using Retrieval-Augmented
                        Generation (RAG), tracks learning progress across
                        sessions, generates quizzes, and creates structured
                        study summaries for effective revision.
                    </p>

                    <div className="hero-buttons">

                        <Link
                            to="/signup"
                            className="primary-btn"
                        >
                            Get Started Free
                        </Link>

                        <Link
                            to="/login"
                            className="secondary-btn"
                        >
                            Login
                        </Link>

                    </div>

                    <div className="hero-stats">

                        <div className="stat-card">
                            <h3>AI Tutor</h3>
                            <p>Personalized Learning</p>
                        </div>

                        <div className="stat-card">
                            <h3>RAG</h3>
                            <p>Learn From PDFs</p>
                        </div>

                        <div className="stat-card">
                            <h3>Memory</h3>
                            <p>Tracks Progress</p>
                        </div>

                    </div>

                </div>

                <div className="hero-right">

                    <div className="ai-window">

                        <div className="window-header">

                            <span className="dot red"></span>
                            <span className="dot yellow"></span>
                            <span className="dot green"></span>

                            <h4>EduMind Assistant</h4>

                        </div>

                        <div className="chat-preview">

                            <div className="user-msg">
                                Explain Binary Search.
                            </div>

                            <div className="bot-msg">
                                Binary Search is an efficient searching
                                algorithm that repeatedly divides the search
                                interval into half. It works only on sorted
                                data and has a time complexity of O(log n).
                            </div>

                            <div className="summary-card">

                                <h4>Session Summary</h4>

                                <ul>
                                    <li>✔ Binary Search</li>
                                    <li>✔ Time Complexity O(log n)</li>
                                    <li>✔ Requires Sorted Arrays</li>
                                    <li>✔ Practice Recommendation</li>
                                </ul>

                            </div>

                        </div>

                    </div>

                </div>

            </section>

            {/* ================= FEATURES ================= */}

            <section
                className="features"
                id="features"
            >

                <h2>Why Choose EduMind?</h2>

                <p className="section-description">
                    A complete AI-powered study assistant designed to help
                    students understand concepts faster and remember them
                    longer.
                </p>

                <div className="feature-grid">

                    <div className="feature-card">

                        <div className="icon">🧠</div>

                        <h3>Adaptive Learning</h3>

                        <p>
                            Explanations automatically adapt to your learning
                            level and previous performance.
                        </p>

                    </div>

                    <div className="feature-card">

                        <div className="icon">📄</div>

                        <h3>Learn From PDFs</h3>

                        <p>
                            Upload notes, books, and lectures. Ask questions
                            directly from your study material.
                        </p>

                    </div>

                    <div className="feature-card">

                        <div className="icon">💬</div>

                        <h3>AI Tutor</h3>

                        <p>
                            Chat naturally with an intelligent tutor that
                            remembers previous conversations.
                        </p>

                    </div>

                    <div className="feature-card">

                        <div className="icon">📝</div>

                        <h3>Smart Quizzes</h3>

                        <p>
                            Generate personalized quizzes based on your study
                            material and previous mistakes.
                        </p>

                    </div>

                    <div className="feature-card">

                        <div className="icon">📊</div>

                        <h3>Progress Tracking</h3>

                        <p>
                            Monitor strengths, weaknesses, and learning
                            progress across every subject.
                        </p>

                    </div>

                    <div className="feature-card">

                        <div className="icon">🔄</div>

                        <h3>Long-Term Memory</h3>

                        <p>
                            Builds a learner profile by tracking strengths,
                            weaknesses, and previous study sessions to
                            deliver increasingly personalized tutoring.
                        </p>

                    </div>

                </div>

            </section>
            {/* ================= HOW IT WORKS ================= */}

            <section className="how-section" id="how">

                <h2>How EduMind Works</h2>

                <p className="section-description">
                    Start learning in just a few simple steps.
                </p>

                <div className="timeline">

                    <div className="timeline-card">
                        <div className="step">1</div>
                        <h3>Create an Account</h3>
                        <p>Sign up and create your personalized learning profile.</p>
                    </div>

                    <div className="timeline-card">
                        <div className="step">2</div>
                        <h3>Create Subjects</h3>
                        <p>Organize your courses into dedicated subjects.</p>
                    </div>

                    <div className="timeline-card">
                        <div className="step">3</div>
                        <h3>Upload Study Material</h3>
                        <p>Upload PDFs, notes, books and lecture slides.</p>
                    </div>

                    <div className="timeline-card">
                        <div className="step">4</div>
                        <h3>Chat with EduMind</h3>
                        <p>Ask questions and receive adaptive explanations.</p>
                    </div>

                    <div className="timeline-card">
                        <div className="step">5</div>
                        <h3>Generate Quizzes</h3>
                        <p>Test yourself using AI-generated quizzes.</p>
                    </div>

                    <div className="timeline-card">
                        <div className="step">6</div>
                        <h3>Track Progress</h3>
                        <p>Review summaries and improve weak concepts.</p>
                    </div>

                </div>

            </section>



            {/* ================= TECHNOLOGY ================= */}

            <section
                className="technology"
                id="technology"
            >

                <h2>Core Technologies Behind EduMind</h2>

                <p className="section-description">
                    EduMind combines modern web technologies, Retrieval-Augmented Generation (RAG),
                    vector search, and adaptive AI tutoring to provide personalized learning
                    experiences based on each student's uploaded study material.
                </p>

                <div className="tech-grid">

                    <div className="tech-grid">

                        <div className="tech-card">
                            ⚛️
                            <span>React</span>
                        </div>

                        <div className="tech-card">
                            ⚡
                            <span>FastAPI</span>
                        </div>

                        <div className="tech-card">
                            🐍
                            <span>Python</span>
                        </div>

                        <div className="tech-card">
                            🗄️
                            <span>PostgreSQL</span>
                        </div>

                        <div className="tech-card">
                            🔎
                            <span>pgvector</span>
                        </div>

                        <div className="tech-card">
                            📚
                            <span>RAG Pipeline</span>
                        </div>

                        <div className="tech-card">
                            🧩
                            <span>SQLAlchemy</span>
                        </div>

                        <div className="tech-card">
                            🧠
                            <span>LLM</span>
                        </div>

                    </div>

                </div>

            </section>



            {/* ================= FAQ ================= */}

            <section
                className="faq"
                id="faq"
            >

                <h2>Frequently Asked Questions</h2>

                <div className="faq-list">

                    <div className="faq-card">
                        <h3>What is EduMind?</h3>
                        <p>
                            Adaptive AI Tutoring using Retrieval-Augmented Generation (RAG)

                            Built as a Final Year Project in Computer Science
                        </p>
                    </div>

                    <div className="faq-card">
                        <h3>Can I upload my own study material?</h3>
                        <p>
                            Yes. Upload PDFs and ask questions directly from your notes.
                        </p>
                    </div>

                    <div className="faq-card">
                        <h3>Does EduMind remember previous sessions?</h3>
                        <p>
                            Yes. It maintains long-term learning memory to personalize
                            future tutoring sessions.
                        </p>
                    </div>

                    <div className="faq-card">
                        <h3>Can it generate quizzes?</h3>
                        <p>
                            Yes. EduMind automatically creates quizzes from your study
                            material and learning history.
                        </p>
                    </div>

                </div>

            </section>



            {/* ================= CALL TO ACTION ================= */}

            <section className="cta">

                <h2>Start Learning Smarter Today</h2>

                <p>
                    Join EduMind and experience personalized AI-powered education.
                </p>

                <div className="cta-buttons">

                    <Link
                        to="/signup"
                        className="primary-btn"
                    >
                        Create Free Account
                    </Link>

                    <Link
                        to="/login"
                        className="secondary-btn"
                    >
                        Login
                    </Link>

                </div>

            </section>



            {/* ================= FOOTER ================= */}

            <footer className="footer">

                <div className="footer-logo">
                    🎓 EduMind AI
                </div>

                <p>
                    AI-Powered Adaptive Learning Platform
                </p>

                <p>
                    Final Year Project • Computer Science
                </p>

                <p className="copyright">
                    © 2026 EduMind AI. All rights reserved.
                </p>

            </footer>

        </div>
    );
}

export default Landing;