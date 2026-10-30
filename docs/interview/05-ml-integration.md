# Milestone 5–6 — Interview Preparation: ML Models & Integration

> **Project:** Helpdesk-AI Enterprise ITSM
> **Milestones:** 5 (model training) and 6 (integration into ticket creation)
> **Audience:** Technical interviews touching applied ML / ML-in-production

---

## Topics Covered

- Model selection for tabular/text classification at small scale
- Graceful degradation when ML fails
- Feature choice for priority/department/SLA prediction
- Storing predictions vs. a separate predictions table
- Retraining and model versioning

---

### Q1. Why scikit-learn models instead of a deep learning approach?

**Answer:** The problem — classify a ticket's priority/department from title+description text, and estimate resolution hours/SLA breach probability — is a small-data, structured-output classification/regression problem, not one that benefits from deep learning's main advantage (learning hierarchical representations from very large unstructured datasets). Scikit-learn models (the project uses classical classifiers/regressors trained in `ml/training/`) train in seconds, are trivially serializable (`.pkl` via `ML_MODEL_PATH`), have no GPU dependency, and are far easier to debug when a prediction looks wrong.

**Follow-up:** When would you reach for deep learning instead? → If the training corpus grew to hundreds of thousands of real tickets with rich free text, and simpler models plateaued below an acceptable accuracy — a transformer-based text classifier would be the natural next step, likely fine-tuned rather than trained from scratch.

---

### Q2. How does the system behave if the ML service throws an exception during ticket creation?

**Answer:** It never blocks ticket creation. `TicketService.create_ticket()` wraps the `ml_service.predict(...)` call in `try/except Exception`, logs the error, and lets ticket creation continue with the prediction fields left `None`. A support ticketing system's core job — let someone report a problem — must not depend on an optional enhancement working.

**In our project:** `predicted_priority_score`, `predicted_sla_breach_prob`, `predicted_resolution_hours` are all nullable columns specifically so "no prediction available" is a valid, expected state, not an error.

**Follow-up:** What's the tradeoff of "fail silently and log"? → You risk predictions quietly being absent for a long time if the ML service is broken and nobody's watching the logs. In a real production system this would pair with an alert on prediction-failure rate, not just a log line.

---

### Q3. What features feed the priority and department predictions?

**Answer:** Ticket `title` and `description` text, passed together into `ml_service.predict()`. No other ticket metadata (reporter, time of day, etc.) is used in the current models — the assumption is that the content of the complaint itself is the strongest signal for both urgency and the right team.

**Follow-up:** What features would you add if accuracy needed improving? → Reporter's historical ticket volume/department, time-of-day/day-of-week (some issue types cluster), and department-specific keyword lists as engineered features alongside the raw text vectorization.

---

### Q4. Why store ML predictions directly on the `tickets` row instead of a separate `ticket_predictions` table?

**Answer:** Predictions here are 1:1 with a ticket and never have their own independent lifecycle (no history of "prediction v1, v2..." is tracked) — they're computed once, at creation, and read alongside the rest of the ticket in nearly every view (`TicketResponse` includes them). A separate table would require a join on every ticket read for no normalization benefit, since there's no repeating group or independent entity here.

**Follow-up:** When would a separate table be justified? → If predictions needed to be re-run and *history* of prediction accuracy tracked over time (e.g., to monitor model drift) — at that point each prediction run becomes its own row with a foreign key back to the ticket, which is a genuinely different data shape (one-to-many).

---

### Q5. How does department auto-assignment interact with a reporter's explicit choice?

**Answer:** It only fires if the reporter left `department_id` unset. `create_ticket()` checks `if ticket.department_id is None and prediction.department_name:` before applying the ML suggestion — a human's explicit choice always wins over the model's guess.

**Follow-up:** Why not let ML override even an explicit choice if it's more confident? → Because the reporter has context the model doesn't (they may know this is a repeat issue routed to a specific team before) — overriding an explicit human decision with a black-box prediction is a trust-eroding UX choice, not just a technical one.

---

### Q6. How would you version and retrain these models safely?

**Answer:** Retraining happens via the scripts in `ml/training/` (one per model — `train_priority.py`, `train_department.py`, `train_sla.py`), writing new `.pkl` files to `ml/models/`. `.gitignore` excludes the `.pkl` artifacts themselves (binary, environment-specific) but not the training scripts. In a more mature setup, each retrain would tag the model artifact with a version/date, and `ml/service.py` would load a specific pinned version rather than "whatever's currently in `ml/models/`" — that pinning is the gap between this project's current state and a production ML deployment.

**Follow-up:** Why exclude `.pkl` files from git specifically? → Binary blobs bloat repo history and diff poorly; a dedicated model registry (or at minimum a release artifact, not a git-tracked file) is the standard pattern once a model needs to be reproducibly deployed.
