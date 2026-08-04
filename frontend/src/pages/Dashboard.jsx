import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import client from "../api/client";
import styles from "./Dashboard.module.css";

const levelColors = {
  beginner: "warning",
  intermediate: "accent",
  advanced: "success",
};

function Dashboard() {
  const [subjects, setSubjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [newSubjectName, setNewSubjectName] = useState("");
  const navigate = useNavigate();

  const fetchSubjects = async () => {
    try {
      const res = await client.get("/subjects/");
      setSubjects(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSubjects();
  }, []);

  const handleCreateSubject = async (e) => {
    e.preventDefault();
    if (!newSubjectName.trim()) return;
    try {
      await client.post("/subjects/", { subject_name: newSubjectName });
      setNewSubjectName("");
      setShowModal(false);
      fetchSubjects();
    } catch (err) {
      console.error(err);
    }
  };

  if (loading) return <div className={styles.loading}>Loading...</div>;

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <p className={styles.title}>Your subjects</p>
          <p className={styles.subtitle}>Pick up where you left off, or start something new.</p>
        </div>
        <button className={styles.newButton} onClick={() => setShowModal(true)}>
          + New subject
        </button>
      </div>

      {subjects.length === 0 ? (
        <div className={styles.empty}>
          <p>No subjects yet. Create one to get started.</p>
        </div>
      ) : (
        <div className={styles.grid}>
          {subjects.map((s) => (
            <div
              key={s.id}
              className={styles.card}
              onClick={() => navigate(`/subjects/${s.id}`)}
            >
              <div className={styles.cardTop}>
                <p className={styles.cardName}>{s.subject_name}</p>
                <span className={`${styles.badge} ${styles[levelColors[s.current_level]]}`}>
                  {s.current_level}
                </span>
              </div>
              <div className={styles.progressTrack}>
                <div
                  className={`${styles.progressFill} ${styles[levelColors[s.current_level]]}`}
                  style={{ width: `${s.confidence_score * 100}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}

      {showModal && (
        <div className={styles.modalOverlay} onClick={() => setShowModal(false)}>
          <form
            className={styles.modal}
            onClick={(e) => e.stopPropagation()}
            onSubmit={handleCreateSubject}
          >
            <p className={styles.modalTitle}>New subject</p>
            <input
              type="text"
              placeholder="e.g. Computer Science"
              value={newSubjectName}
              onChange={(e) => setNewSubjectName(e.target.value)}
              className={styles.input}
              autoFocus
            />
            <div className={styles.modalActions}>
              <button type="button" onClick={() => setShowModal(false)} className={styles.cancelButton}>
                Cancel
              </button>
              <button type="submit" className={styles.newButton}>
                Create
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

export default Dashboard;