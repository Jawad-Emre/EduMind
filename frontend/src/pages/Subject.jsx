import { useEffect, useState, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import "highlight.js/styles/github.css";
import client from "../api/client";
import styles from "./Subject.module.css";

function CodeBlock({ className, children }) {
    const language = className?.replace("hljs language-", "").replace("language-", "") || "text";
    const codeText = String(children).replace(/\n$/, "");

    const handleCopy = () => {
        navigator.clipboard.writeText(codeText);
    };

    return (
        <div className={styles.codeBlockWrapper}>
            <div className={styles.codeBlockHeader}>
                <span>{language}</span>
                <button className={styles.copyButton} onClick={handleCopy}>
                    Copy
                </button>
            </div>
            <pre>
                <code className={className}>{children}</code>
            </pre>
        </div>
    );
}

function MarkdownTable({ children }) {
    return (
        <div className={styles.tableWrapper}>
            <table>{children}</table>
        </div>
    );
}

const markdownComponents = {
    code: CodeBlock,
    table: MarkdownTable,
};

function humanizeKey(key) {
    return key.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

function SummaryModal({ summary, loading, error, onClose }) {
    const structured = summary?.structured || {};
    const listSections = Object.entries(structured).filter(
        ([key, value]) => Array.isArray(value) && key !== "summary_text"
    );

    return (
        <div className={styles.modalOverlay} onClick={onClose}>
            <div className={styles.modalCard} onClick={(e) => e.stopPropagation()}>
                <div className={styles.modalHeader}>
                    <p className={styles.modalTitle}>Chat summary</p>
                    <button className={styles.modalClose} onClick={onClose}>
                        ×
                    </button>
                </div>

                {loading && <p className={styles.emptyChat}>Summarizing…</p>}
                {error && <p className={styles.summaryError}>{error}</p>}

                {!loading && !error && summary && (
                    <>
                        <div className={styles.summarySection}>
                            <p>{summary.summary_text}</p>
                        </div>

                        {listSections.map(([key, items]) => (
                            <div key={key} className={styles.summarySection}>
                                <p className={styles.summarySectionTitle}>{humanizeKey(key)}</p>
                                <ul className={styles.summaryList}>
                                    {items.map((item, i) => (
                                        <li key={i}>{item}</li>
                                    ))}
                                </ul>
                            </div>
                        ))}
                    </>
                )}
            </div>
        </div>
    );
}

function Subject() {
    const { subjectId } = useParams();
    const navigate = useNavigate();
    const [activeTab, setActiveTab] = useState("chat");
    const [subject, setSubject] = useState(null);
    const [sessionId, setSessionId] = useState(null);
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState("");
    const [sending, setSending] = useState(false);
    const [pastSessions, setPastSessions] = useState([]);
    const [viewingSessionId, setViewingSessionId] = useState(null);
    const messagesEndRef = useRef(null);
    const [materials, setMaterials] = useState([]);
    const [uploading, setUploading] = useState(false);
    const fileInputRef = useRef(null);
    const sessionStarting = useRef(false);
    const [sidebarOpen, setSidebarOpen] = useState(false);

    const [quiz, setQuiz] = useState(null);
    const [quizAnswers, setQuizAnswers] = useState({});
    const [quizResult, setQuizResult] = useState(null);
    const [generatingQuiz, setGeneratingQuiz] = useState(false);
    const [quizCount, setQuizCount] = useState(5);

    const [summaryLoading, setSummaryLoading] = useState(false);
    const [endingSession, setEndingSession] = useState(false);

    useEffect(() => {
        fetchSubject();
        startSession();
    }, [subjectId]);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    useEffect(() => {
        if (activeTab === "materials") fetchMaterials();
    }, [activeTab]);

    const fetchSubject = async () => {
        try {
            const res = await client.get("/subjects/");
            const found = res.data.find((s) => s.id === parseInt(subjectId));
            setSubject(found);
        } catch (err) {
            console.error(err);
        }
    };

    const startSession = async () => {
        if (sessionStarting.current) return;
        sessionStarting.current = true;

        try {
            const res = await client.get(`/sessions/?subject_id=${subjectId}`);
            const sessions = res.data;
            setPastSessions(sessions.filter((s) => s.ended_at !== null));

            const openSession = sessions.find((s) => s.ended_at === null);

            if (openSession) {
                setSessionId(openSession.id);
                setViewingSessionId(openSession.id);
                const msgRes = await client.get(`/messages/session/${openSession.id}`);
                setMessages(msgRes.data.map((m) => ({ role: m.role, content: m.content })));
            } else {
                const newSession = await client.post("/sessions/", { subject_id: parseInt(subjectId) });
                setSessionId(newSession.data.id);
                setViewingSessionId(newSession.data.id);
            }
        } catch (err) {
            console.error(err);
        } finally {
            sessionStarting.current = false;
        }
    };

    const viewPastSession = async (id) => {
        setViewingSessionId(id);
        setActiveTab("chat");
        setSidebarOpen(false);
        const msgRes = await client.get(`/messages/session/${id}`);
        setMessages(msgRes.data.map((m) => ({ role: m.role, content: m.content })));
    };

    const handleNewChat = async () => {
        if (sessionId) {
            try {
                await client.patch(`/sessions/${sessionId}/end`);
                setPastSessions((prev) => [
                    { id: sessionId, started_at: new Date().toISOString(), ended_at: new Date().toISOString() },
                    ...prev,
                ]);
            } catch (err) {
                console.error(err);
            }
        }
        setMessages([]);
        setActiveTab("chat");
        setSidebarOpen(false);
        const newSession = await client.post("/sessions/", { subject_id: parseInt(subjectId) });
        setSessionId(newSession.data.id);
        setViewingSessionId(newSession.data.id);
    };

    const isViewingActive = viewingSessionId === sessionId;
    const currentSessionLabel =
        messages.find((m) => m.role === "user")?.content?.slice(0, 30) || "New chat";

    const handleSend = async () => {
        if (!input.trim() || !sessionId || sending) return;
        const userMessage = input;
        setInput("");
        setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
        setSending(true);

        try {
            const res = await client.post("/chat/", {
                session_id: sessionId,
                content: userMessage,
            });
            setMessages((prev) => [...prev, { role: "assistant", content: res.data.answer }]);
            fetchSubject();
        } catch (err) {
            setMessages((prev) => [
                ...prev,
                {
                    role: "assistant",
                    content: err.response?.data?.detail || "Something went wrong. Please try again.",
                },
            ]);
        } finally {
            setSending(false);
        }
    };

    const handleKeyDown = (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    const fetchMaterials = async () => {
        try {
            const res = await client.get(`/documents/?subject_id=${subjectId}`);
            setMaterials(res.data);
        } catch (err) {
            console.error(err);
        }
    };

    const handleFileUpload = async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        const formData = new FormData();
        formData.append("file", file);
        formData.append("subject_id", subjectId);

        setUploading(true);
        try {
            await client.post("/documents/upload", formData, {
                headers: { "Content-Type": "multipart/form-data" },
            });
            fetchMaterials();
            pollMaterialStatus();
        } catch (err) {
            console.error(err);
        } finally {
            setUploading(false);
            if (fileInputRef.current) fileInputRef.current.value = "";
        }
    };

    const pollMaterialStatus = () => {
        const interval = setInterval(async () => {
            try {
                const res = await client.get(`/documents/?subject_id=${subjectId}`);
                setMaterials(res.data);
                const stillProcessing = res.data.some((m) => m.upload_status === "processing");
                if (!stillProcessing) clearInterval(interval);
            } catch (err) {
                console.error("Polling error:", err);
            }
        }, 3000);
        setTimeout(() => clearInterval(interval), 60000);
    };

    const handleGenerateQuiz = async (source) => {
        setGeneratingQuiz(true);
        setQuiz(null);
        setQuizResult(null);
        setQuizAnswers({});

        const payload = { subject_id: parseInt(subjectId), num_questions: quizCount };
        if (source === "material") {
            const readyMaterial = materials.find((m) => m.upload_status === "ready");
            if (!readyMaterial) {
                alert("No ready material available yet.");
                setGeneratingQuiz(false);
                return;
            }
            payload.material_id = readyMaterial.id;
        } else {
            payload.session_id = sessionId;
        }

        try {
            const res = await client.post("/quizzes/generate", payload);
            setQuiz(res.data);
        } catch (err) {
            console.error(err);
            alert(err.response?.data?.detail || "Quiz generation failed");
        } finally {
            setGeneratingQuiz(false);
        }
    };

    const handleSummarize = async () => {
        if (!viewingSessionId || summaryLoading) return;

        setSummaryLoading(true);

        try {
            const res = await client.post(`/sessions/${viewingSessionId}/summary`);
            const data = res.data;

            let content = "# 📄 Chat Summary\n\n";

            if (data.summary_text) {
                content += `${data.summary_text}\n\n`;
            }

            if (data.topics_covered?.length) {
                content += "## 📚 Topics Covered\n";
                data.topics_covered.forEach((item) => {
                    content += `- ${item}\n`;
                });
                content += "\n";
            }

            if (data.understood_well?.length) {
                content += "## ✅ Concepts You Understood Well\n";
                data.understood_well.forEach((item) => {
                    content += `- ${item}\n`;
                });
                content += "\n";
            }

            if (data.struggled_with?.length) {
                content += "## ⚠️ Concepts to Review\n";
                data.struggled_with.forEach((item) => {
                    content += `- ${item}\n`;
                });
                content += "\n";
            }

            if (data.review_suggestions?.length) {
                content += "## 📖 Suggested Revision\n";
                data.review_suggestions.forEach((item) => {
                    content += `- ${item}\n`;
                });
                content += "\n";
            }

            setMessages((prev) => [
                ...prev,
                {
                    role: "assistant",
                    content,
                },
            ]);
        } catch (err) {
            console.error(err);

            setMessages((prev) => [
                ...prev,
                {
                    role: "assistant",
                    content:
                        err.response?.data?.detail ||
                        "Summary generation failed.",
                },
            ]);
        } finally {
            setSummaryLoading(false);
        }
    };

    const handleEndSession = async () => {
        if (!sessionId || endingSession) return;
        if (!window.confirm("End this session? EduMind will review the chat and update your profile if it was useful.")) {
            return;
        }

        setEndingSession(true);
        try {
            // Ending the session triggers the backend summary + profile update.
            await client.patch(`/sessions/${sessionId}/end`);
            setPastSessions((prev) => [
                { id: sessionId, started_at: new Date().toISOString(), ended_at: new Date().toISOString() },
                ...prev,
            ]);

            // Start a fresh session so the user can keep chatting.
            setMessages([]);
            const newSession = await client.post("/sessions/", { subject_id: parseInt(subjectId) });
            setSessionId(newSession.data.id);
            setViewingSessionId(newSession.data.id);
            setActiveTab("chat");
            fetchSubject();
        } catch (err) {
            console.error(err);
            alert(err.response?.data?.detail || "Could not end the session. Please try again.");
        } finally {
            setEndingSession(false);
        }
    };

    const handleSelectAnswer = (questionIndex, optionText) => {
        setQuizAnswers((prev) => ({ ...prev, [questionIndex]: optionText }));
    };

    const handleSubmitQuiz = async () => {
        const answers = quiz.questions.map((_, i) => quizAnswers[i] || "");
        try {
            const res = await client.post(`/quizzes/${quiz.id}/submit`, { answers });
            setQuizResult(res.data);
            fetchSubject();
        } catch (err) {
            console.error(err);
        }
    };

    if (!subject) return <div className={styles.loading}>Loading...</div>;

    return (
        <div className={styles.appShell}>
            <button className={styles.mobileMenuButton} onClick={() => setSidebarOpen(true)}>
                ☰
            </button>

            {sidebarOpen && <div className={styles.sidebarOverlay} onClick={() => setSidebarOpen(false)} />}

            <div className={`${styles.sidebar} ${sidebarOpen ? styles.sidebarOpen : ""}`}>
                <div className={styles.sidebarTop}>
                    <span className={styles.backLink} onClick={() => navigate("/dashboard")}>
                        ← Subjects
                    </span>
                    <button className={styles.sidebarCloseButton} onClick={() => setSidebarOpen(false)}>
                        ×
                    </button>
                </div>

                <button className={styles.newChatButton} onClick={handleNewChat}>
                    + New chat
                </button>

                <div className={styles.subjectCard}>
                    <p className={styles.subjectCardName}>{subject.subject_name}</p>
                    <p className={styles.subjectCardMeta}>
                        {subject.current_level} · Confidence {subject.confidence_score.toFixed(2)}
                    </p>
                </div>

                <p className={styles.sidebarLabel}>Sessions</p>
                <div className={styles.sessionList}>
                    <div
                        className={`${styles.sessionItem} ${isViewingActive ? styles.sessionActive : ""}`}
                        onClick={() => viewPastSession(sessionId)}
                    >
                        <p className={styles.sessionDate}>
                            {isViewingActive ? currentSessionLabel : "Current"}
                        </p>
                        <p className={styles.sessionMeta}>Active</p>
                    </div>
                    {pastSessions.map((s) => (
                        <div
                            key={s.id}
                            className={`${styles.sessionItem} ${viewingSessionId === s.id ? styles.sessionActive : ""}`}
                            onClick={() => viewPastSession(s.id)}
                        >
                            <p className={styles.sessionDate}>
                                {new Date(s.started_at).toLocaleDateString()}
                            </p>
                            <p className={styles.sessionMeta}>
                                {new Date(s.started_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                            </p>
                        </div>
                    ))}
                </div>
            </div>

            <div className={styles.main}>
                <div className={styles.mainInner}>
                    <div className={styles.tabs}>
                        <div
                            className={`${styles.tab} ${activeTab === "chat" ? styles.tabActive : ""}`}
                            onClick={() => setActiveTab("chat")}
                        >
                            Chat
                        </div>
                        <div
                            className={`${styles.tab} ${activeTab === "materials" ? styles.tabActive : ""}`}
                            onClick={() => setActiveTab("materials")}
                        >
                            Materials
                        </div>
                        <div
                            className={`${styles.tab} ${activeTab === "quiz" ? styles.tabActive : ""}`}
                            onClick={() => setActiveTab("quiz")}
                        >
                            Quizzes
                        </div>

                        {activeTab === "chat" && messages.length > 0 && (
                            <button
                                className={styles.summaryButton}
                                onClick={handleSummarize}
                                disabled={summaryLoading}
                            >
                                {summaryLoading ? "Summarizing…" : "Summarize this chat"}
                            </button>
                        )}

                        {isViewingActive && (
                            <button
                                className={styles.endSessionButton}
                                onClick={handleEndSession}
                                disabled={endingSession}
                            >
                                {endingSession ? "Ending…" : "End session"}
                            </button>
                        )}
                    </div>

                    {activeTab === "chat" && (
                        <div className={styles.chatArea}>
                            <div className={styles.messages}>
                                {messages.length === 0 && (
                                    <p className={styles.emptyChat}>Ask a question to get started.</p>
                                )}
                                {messages.map((m, i) =>
                                    m.role === "assistant" ? (
                                        <div key={i} className={styles.assistantRow}>
                                            <div className={styles.avatar}>AI</div>
                                            <div className={styles.assistantBubble}>
                                                <ReactMarkdown
                                                    remarkPlugins={[remarkGfm]}
                                                    rehypePlugins={[rehypeHighlight]}
                                                    components={markdownComponents}
                                                >
                                                    {m.content}
                                                </ReactMarkdown>
                                            </div>
                                        </div>
                                    ) : (
                                        <div key={i} className={styles.userBubble}>
                                            {m.content}
                                        </div>
                                    )
                                )}
                                {sending && (
                                    <div className={styles.assistantRow}>
                                        <div className={styles.avatar}>AI</div>
                                        <div className={styles.typing}>EduMind is thinking...</div>
                                    </div>
                                )}
                                <div ref={messagesEndRef} />
                            </div>

                            {!isViewingActive && (
                                <p className={styles.readOnlyNotice}>Viewing a past session — read only.</p>
                            )}

                            <div className={styles.inputRow}>
                                <input
                                    type="text"
                                    placeholder="Ask a question..."
                                    value={input}
                                    onChange={(e) => setInput(e.target.value)}
                                    onKeyDown={handleKeyDown}
                                    disabled={sending || !isViewingActive}
                                    className={styles.chatInput}
                                />
                                <button onClick={handleSend} disabled={sending || !isViewingActive} className={styles.sendButton}>
                                    →
                                </button>
                            </div>
                        </div>
                    )}

                    {activeTab === "materials" && (
                        <div>
                            <div className={styles.dropzone} onClick={() => fileInputRef.current?.click()}>
                                <p className={styles.dropzoneText}>
                                    {uploading ? "Uploading..." : "Click to browse, or drag a file here"}
                                </p>
                                <p className={styles.dropzoneHint}>PDF, DOCX, PNG, JPG — up to 20MB</p>
                                <input
                                    type="file"
                                    ref={fileInputRef}
                                    onChange={handleFileUpload}
                                    style={{ display: "none" }}
                                    accept=".pdf,.docx,.png,.jpg,.jpeg"
                                />
                            </div>

                            {materials.length === 0 ? (
                                <p className={styles.emptyChat}>No materials uploaded yet.</p>
                            ) : (
                                <div className={styles.materialsList}>
                                    {materials.map((m) => (
                                        <div key={m.id} className={styles.materialRow}>
                                            <span className={styles.materialIcon}>📄</span>
                                            <div className={styles.materialInfo}>
                                                <p className={styles.materialName}>{m.filename}</p>
                                            </div>
                                            <span
                                                className={`${styles.statusBadge} ${m.upload_status === "ready"
                                                    ? styles.statusReady
                                                    : m.upload_status === "failed"
                                                        ? styles.statusFailed
                                                        : styles.statusProcessing
                                                    }`}
                                            >
                                                {m.upload_status}
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}

                    {activeTab === "quiz" && (
                        <div>
                            {!quiz && !generatingQuiz && (
                                <div className={styles.quizStart}>
                                    <p className={styles.emptyChat}>Generate a quiz to test your understanding.</p>
                                    <div className={styles.quizCountRow}>
                                        <label htmlFor="quizCount" className={styles.quizCountLabel}>
                                            Number of questions
                                        </label>
                                        <select
                                            id="quizCount"
                                            className={styles.quizCountSelect}
                                            value={quizCount}
                                            onChange={(e) => setQuizCount(parseInt(e.target.value))}
                                        >
                                            <option value={5}>5</option>
                                            <option value={10}>10</option>
                                            <option value={15}>15</option>
                                            <option value={20}>20</option>
                                        </select>
                                    </div>
                                    <div className={styles.quizStartButtons}>
                                        <button className={styles.newChatButton} onClick={() => handleGenerateQuiz("material")}>
                                            From uploaded material
                                        </button>
                                        <button className={styles.secondaryButton} onClick={() => handleGenerateQuiz("chat")}>
                                            From this chat
                                        </button>
                                    </div>
                                </div>
                            )}

                            {generatingQuiz && <p className={styles.emptyChat}>Generating quiz...</p>}

                            {quiz && !quizResult && (
                                <div>
                                    {quiz.questions.map((q, qi) => (
                                        <div key={qi} className={styles.quizQuestion}>
                                            <p className={styles.quizQuestionText}>
                                                {qi + 1}. {q.question}
                                            </p>
                                            <div className={styles.quizOptions}>
                                                {q.options.map((opt, oi) => (
                                                    <label
                                                        key={oi}
                                                        className={`${styles.quizOption} ${quizAnswers[qi] === opt.text ? styles.quizOptionSelected : ""
                                                            }`}
                                                    >
                                                        <input
                                                            type="radio"
                                                            name={`q${qi}`}
                                                            checked={quizAnswers[qi] === opt.text}
                                                            onChange={() => handleSelectAnswer(qi, opt.text)}
                                                        />
                                                        {opt.text}
                                                    </label>
                                                ))}
                                            </div>
                                        </div>
                                    ))}
                                    <button className={styles.newChatButton} onClick={handleSubmitQuiz}>
                                        Submit quiz
                                    </button>
                                </div>
                            )}

                            {quizResult && (
                                <div>
                                    <div className={styles.resultSummary}>
                                        <p className={styles.resultScore}>
                                            {Math.round(quizResult.score * quizResult.questions.length)} / {quizResult.questions.length}
                                        </p>
                                        <p className={styles.emptyChat}>Confidence updated</p>
                                    </div>
                                    {quizResult.questions.map((q, qi) => (
                                        <div key={qi} className={styles.quizQuestion}>
                                            <p className={styles.quizQuestionText}>{q.question}</p>
                                            {q.options.map((opt, oi) => (
                                                <div
                                                    key={oi}
                                                    className={`${styles.resultOption} ${opt.is_correct ? styles.resultCorrect : ""}`}
                                                >
                                                    <p className={styles.resultOptionText}>
                                                        {opt.text} {quizAnswers[qi] === opt.text ? "· Your answer" : ""}
                                                    </p>
                                                    <p className={styles.resultExplanation}>{opt.explanation}</p>
                                                </div>
                                            ))}
                                        </div>
                                    ))}
                                    <button
                                        className={styles.newChatButton}
                                        onClick={() => {
                                            setQuiz(null);
                                            setQuizResult(null);
                                        }}
                                    >
                                        Back
                                    </button>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

export default Subject;