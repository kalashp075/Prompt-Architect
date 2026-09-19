import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";

import { supabase } from "./supabase";

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const sessionStorageKey = "prompt-architect-session";
const sessionTokenStorageKey = "prompt-architect-session-token";
const categories = [
  ["general", "General", "A flexible prompt for any kind of project."],
  ["design", "Design / UI", "Shape thoughtful interfaces and experiences."],
  ["frontend", "Frontend", "Plan polished, responsive client experiences."],
  ["backend", "Backend", "Architect reliable APIs and services."],
  ["fullstack", "Full Stack", "Connect the complete product system."],
];
const listFields = ["requirements", "preferences", "constraints", "assumptions"];
const maxInputLength = 4000;

class ApiError extends Error {
  constructor(message, { code, status } = {}) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

async function request(path, options = {}) {
  const { data: authData } = supabase ? await supabase.auth.getSession() : { data: { session: null } };
  const { headers: optionHeaders, ...requestOptions } = options;
  const headers = { "Content-Type": "application/json", ...(optionHeaders || {}) };
  if (authData.session?.access_token) {
    headers.Authorization = `Bearer ${authData.session.access_token}`;
    delete headers["X-Session-Token"];
  } else {
    const sessionToken = localStorage.getItem(sessionTokenStorageKey);
    if (sessionToken) headers["X-Session-Token"] = sessionToken;
  }
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 90000);
  const response = await fetch(`${apiBaseUrl}${path}`, { ...requestOptions, headers, signal: controller.signal })
    .catch((error) => {
      if (error.name === "AbortError") throw new ApiError("The request took too long. Please try again.", { code: "timeout" });
      throw new ApiError("Can't reach the server right now.", { code: "network_error" });
    })
    .finally(() => clearTimeout(timeout));
  let data;
  try {
    data = await response.json();
  } catch {
    throw new ApiError(
      response.status === 401 ? "Your login has expired. Please log in again." : "The server returned an invalid response.",
      { code: response.status === 401 ? "auth_error" : "server_error", status: response.status },
    );
  }
  if (!response.ok) {
    throw new ApiError(data.error?.message || data.detail || "Request failed.", {
      code: response.status === 401 ? "auth_error" : data.error?.code,
      status: response.status,
    });
  }
  return data;
}

function Icon({ name, size = 18 }) {
  const paths = {
    arrow: <><path d="M5 12h14" /><path d="m13 6 6 6-6 6" /></>,
    menu: <><path d="M4 6h16" /><path d="M4 12h16" /><path d="M4 18h16" /></>,
    plus: <><path d="M12 5v14" /><path d="M5 12h14" /></>,
    spark: <><path d="m12 3-1.3 5.7L5 10l5.7 1.3L12 17l1.3-5.7L19 10l-5.7-1.3L12 3Z" /><path d="m19 16-.5 2.5L16 19l2.5.5L19 22l.5-2.5L22 19l-2.5-.5L19 16Z" /></>,
    clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
    logout: <><path d="M10 17l5-5-5-5" /><path d="M15 12H3" /><path d="M21 19V5a2 2 0 0 0-2-2h-6" /></>,
    copy: <><rect width="13" height="13" x="8" y="8" rx="2" /><path d="M4 16V5a2 2 0 0 1 2-2h11" /></>,
    download: <><path d="M12 3v12" /><path d="m7 10 5 5 5-5" /><path d="M5 21h14" /></>,
    check: <path d="m5 12 4 4L19 6" />,
    chevron: <path d="m6 9 6 6 6-6" />,
  };
  return <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>;
}

function Spinner({ label }) {
  return <span className="inline-flex items-center gap-2"><span className="spinner" />{label}</span>;
}

function ErrorMessage({ error, onRetry }) {
  const navigate = useNavigate();
  useEffect(() => {
    if (error?.code === "auth_error") {
      supabase?.auth.signOut();
      navigate("/login", { state: { message: "Your login has expired. Please log in again." } });
    }
  }, [error, navigate]);
  if (!error) return null;
  let message = error.message;
  if (error.code === "rate_limited") message = "We've hit the request limit for now — please wait a moment and try again.";
  if (error.code === "malformed_json") message = "Something went wrong understanding your idea — try rephrasing it or try again.";
  if (error.code === "network_error") message = "Can't reach the server right now.";
  return (
    <div className="error-panel" role="alert">
      <span className="error-dot">!</span>
      <div className="min-w-0 flex-1"><p>{message}</p>{error.code === "auth_error" ? <Link className="mt-2 inline-block underline" to="/login">Log in again</Link> : null}</div>
      {onRetry ? <button type="button" onClick={onRetry} className="button button-light button-small">Try again</button> : null}
    </div>
  );
}

function Brand() {
  return <Link to="/" className="brand"><span className="brand-mark"><Icon name="spark" size={16} /></span><span>Prompt Architect</span></Link>;
}

function Sidebar({ sessions, isLoading, onClose }) {
  const location = useLocation();
  return (
    <aside className="sidebar">
      <div className="sidebar-top"><Brand /><button className="icon-button mobile-only" onClick={onClose} aria-label="Close navigation">×</button></div>
      <Link to="/" onClick={onClose} className="new-prompt-button"><Icon name="plus" size={17} /> New prompt</Link>
      <div className="sidebar-label"><span>Workspace</span></div>
      <nav className="sidebar-nav">
        <Link to="/" onClick={onClose} className={location.pathname === "/" ? "active" : ""}><Icon name="spark" size={17} /> Create prompt</Link>
        <Link to="/sessions" onClick={onClose} className={location.pathname === "/sessions" ? "active" : ""}><Icon name="clock" size={17} /> History</Link>
      </nav>
      <div className="sidebar-label history-heading"><span>Recent prompts</span><span className="muted-count">{sessions?.length || 0}</span></div>
      <div className="history-list">
        {isLoading ? <><div className="skeleton-line" /><div className="skeleton-line short" /></> : sessions?.slice(0, 6).map((session) => (
          <Link key={session.id} onClick={onClose} to={`/sessions/${session.id}`} className="history-item">
            <span className="history-title">{session.raw_input}</span>
            <span className="history-meta">{session.target_category} <span>·</span> {session.status.replaceAll("_", " ")}</span>
          </Link>
        ))}
        {!isLoading && !sessions?.length ? <p className="sidebar-empty">Your saved prompts will appear here.</p> : null}
      </div>
      <div className="sidebar-bottom"><p className="sidebar-tip"><Icon name="spark" size={15} /> Turn rough ideas into clear direction.</p></div>
    </aside>
  );
}

function Topbar({ authSession, onMenu, onLogout }) {
  const [profileOpen, setProfileOpen] = useState(false);
  const profileRef = useRef(null);
  useEffect(() => {
    const closeProfile = (event) => {
      if (profileRef.current && !profileRef.current.contains(event.target)) setProfileOpen(false);
    };
    document.addEventListener("mousedown", closeProfile);
    return () => document.removeEventListener("mousedown", closeProfile);
  }, []);
  return <header className="topbar"><button className="icon-button mobile-only" onClick={onMenu} aria-label="Open navigation"><Icon name="menu" /></button><div className="topbar-spacer" /><div className="topbar-actions">{authSession ? <><Link to="/sessions" className="topbar-link">My history</Link><div ref={profileRef} className="profile-menu"><button type="button" className="avatar profile-trigger" onClick={() => setProfileOpen((open) => !open)} aria-expanded={profileOpen} aria-haspopup="menu">{(authSession.user.email || "U")[0].toUpperCase()}</button>{profileOpen ? <div className="profile-popover" role="menu"><p>{authSession.user.email}</p><button type="button" onClick={onLogout} role="menuitem">Log out</button></div> : null}</div></> : <><Link to="/login" className="topbar-link">Log in</Link><Link to="/signup" className="button button-dark button-small">Get started <Icon name="arrow" size={15} /></Link></>}</div></header>;
}

function AppShell({ children, authSession, sessions, sessionsLoading, onLogout }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  return <div className="app-shell"><div className={mobileOpen ? "mobile-backdrop open" : "mobile-backdrop"} onClick={() => setMobileOpen(false)} /><div className={mobileOpen ? "sidebar-wrap open" : "sidebar-wrap"}><Sidebar sessions={sessions} isLoading={sessionsLoading} onClose={() => setMobileOpen(false)} /></div><div className="main-column"><Topbar authSession={authSession} onMenu={() => setMobileOpen(true)} onLogout={onLogout} /><main className="page-content">{children}</main><footer className="site-footer"><span>Prompt Architect</span><nav className="footer-links"><Link to="/docs">Docs</Link><span>|</span><Link to="/privacy">Privacy Policy</Link><span>|</span><Link to="/terms">Terms</Link><span>|</span><Link to="/security">Security</Link><span>|</span><Link to="/faqs">FAQs</Link></nav></footer></div></div>;
}

function AuthScreen({ mode, onAuthenticated }) {
  const [email, setEmail] = useState(""); const [password, setPassword] = useState(""); const [error, setError] = useState(null); const [pending, setPending] = useState(false);
  const isSignup = mode === "signup"; const location = useLocation(); const [notice] = useState(location.state?.message || "");
  const submit = async (event) => {
    event.preventDefault(); setPending(true); setError(null);
    if (!supabase) { setError(new Error("Supabase frontend variables are not configured.")); setPending(false); return; }
    try {
      const result = isSignup ? await supabase.auth.signUp({ email, password }) : await supabase.auth.signInWithPassword({ email, password });
      if (result.error) setError(result.error); else if (result.data.session) onAuthenticated(); else setError(new Error("Check your email to confirm the account, then log in."));
    } catch { setError(new Error("Can't reach the authentication service right now. Please try again.")); } finally { setPending(false); }
  };
  return <div className="auth-layout"><div className="auth-copy"><span className="eyebrow"><span className="eyebrow-dot" /> A calmer way to prompt</span><h1>{isSignup ? "Give your ideas a clearer voice." : "Welcome back to your ideas."}</h1><p>Turn the first messy thought into a focused brief your tools can actually use.</p></div><form onSubmit={submit} className="auth-card"><div className="auth-card-header"><span className="brand-mark"><Icon name="spark" size={16} /></span><span className="eyebrow">Your workspace</span></div><h2>{isSignup ? "Create your account" : "Log in to Prompt Architect"}</h2><p className="form-subtitle">{isSignup ? "Save your prompts and pick up where you left off." : "Your prompt history is waiting for you."}</p><label>Email<input type="email" required value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" /></label><label>Password<input type="password" required minLength={6} value={password} onChange={(event) => setPassword(event.target.value)} placeholder="At least 6 characters" /></label><button disabled={pending} className="button button-dark full-width">{pending ? <Spinner label="Working..." /> : isSignup ? "Create account" : "Log in"} <Icon name="arrow" size={16} /></button>{notice ? <p className="notice">{notice}</p> : null}<ErrorMessage error={error} /><p className="auth-switch">{isSignup ? "Already have an account?" : "New to Prompt Architect?"} <Link to={isSignup ? "/login" : "/signup"}>{isSignup ? "Log in" : "Create an account"}</Link></p></form></div>;
}

function StepHeader({ eyebrow, title, subtitle }) {
  return <div className="step-header"><span className="eyebrow"><span className="eyebrow-dot" /> {eyebrow}</span><h1>{title}</h1>{subtitle ? <p>{subtitle}</p> : null}</div>;
}

function BackButton({ onClick, disabled = false }) {
  return <button type="button" className="flow-back" onClick={onClick} disabled={disabled}><span aria-hidden="true">←</span> Back</button>;
}

function WizardProgress({ current }) {
  const steps = ["Start", "Questions", "Refine", "Review", "Ready"];
  return <div className="wizard-progress" aria-label={`Step ${current + 1} of ${steps.length}: ${steps[current]}`}><div className="wizard-progress-track"><span style={{ width: `${(current / (steps.length - 1)) * 100}%` }} /></div><div className="wizard-progress-labels">{steps.map((step, index) => <span key={step} className={index <= current ? "complete" : ""}>{step}</span>)}</div></div>;
}

function InputScreen({ onCreated }) {
  const [rawInput, setRawInput] = useState(""); const [category, setCategory] = useState("general"); const [validationError, setValidationError] = useState(""); const [targetOpen, setTargetOpen] = useState(false);
  const targetRef = useRef(null);
  const mutation = useMutation({ mutationFn: (body) => request("/api/sessions/", { method: "POST", body: JSON.stringify(body) }), onSuccess: (session) => onCreated(session) });
  useEffect(() => {
    const closeTarget = (event) => {
      if (targetRef.current && !targetRef.current.contains(event.target)) setTargetOpen(false);
    };
    const closeOnEscape = (event) => {
      if (event.key === "Escape") setTargetOpen(false);
    };
    document.addEventListener("mousedown", closeTarget);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", closeTarget);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, []);
  const submit = (event) => { event.preventDefault(); const length = rawInput.trim().length; if (length < 10) { setValidationError("Please enter at least 10 characters."); return; } if (length > maxInputLength) { setValidationError(`Please keep your idea under ${maxInputLength} characters.`); return; } setValidationError(""); mutation.mutate({ raw_input: rawInput.trim(), target_category: category }); };
  const selectedCategory = categories.find(([value]) => value === category);
  return <div className="flow-container"><StepHeader eyebrow="Start with a thought" title={<>What are you <em>building?</em></>} subtitle="Describe the idea in your own words. Prompt Architect will help you find the shape inside it." /><form onSubmit={submit} className="prompt-form"><div className="textarea-wrap"><textarea value={rawInput} onChange={(event) => setRawInput(event.target.value)} rows={7} placeholder="I want to build..." autoFocus /><div className="composer-controls"><div ref={targetRef} className="target-menu"><button type="button" className="target-picker" onClick={() => setTargetOpen((open) => !open)} aria-expanded={targetOpen} aria-haspopup="listbox"><span>Prompt target:</span><strong>{selectedCategory[1]}</strong><Icon name="chevron" size={15} /></button>{targetOpen ? <div className="target-popover" role="listbox" aria-label="Prompt target options">{categories.map(([value, label, description]) => <button type="button" role="option" aria-selected={category === value} key={value} className={category === value ? "target-option selected" : "target-option"} onClick={() => { setCategory(value); setTargetOpen(false); }}><span className="target-option-copy"><strong>{label}</strong><small>{description}</small></span>{category === value ? <Icon name="check" size={17} /> : null}</button>)}</div> : null}</div><span className="textarea-count">{rawInput.length}/{maxInputLength}</span></div></div>{validationError ? <p className="field-error" role="alert">{validationError}</p> : null}<div className="form-footer"><span className="privacy-note"><span className="lock-dot">✦</span> Your idea stays private</span><button disabled={mutation.isPending} className="button button-dark">{mutation.isPending ? <Spinner label="Analyzing your idea..." /> : <>Analyze my idea <Icon name="arrow" size={16} /></>}</button></div><ErrorMessage error={mutation.error} onRetry={() => mutation.mutate(mutation.variables)} /></form></div>;
}

function QuestionsScreen({ session, onDone, onBack }) {
  const [answer, setAnswer] = useState("");
  const [historyOpen, setHistoryOpen] = useState(false);
  useEffect(() => {
    setAnswer("");
  }, [session.current_question]);
  const answerMutation = useMutation({
    mutationFn: (body) => request(`/api/sessions/${session.id}/question-answer/`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
    onSuccess: onDone,
  });
  const assumptionsMutation = useMutation({
    mutationFn: () => request(`/api/sessions/${session.id}/assumptions/`, { method: "POST" }),
    onSuccess: onDone,
  });
  const isPending = answerMutation.isPending || assumptionsMutation.isPending;
  const history = session.specification.answers || [];
  const submitAnswer = (event, skipped = false) => {
    event?.preventDefault();
    answerMutation.mutate(skipped ? { skipped: true } : { answer: answer.trim() });
  };
  return (
    <div className="flow-container narrow-flow">
      <WizardProgress current={1} />
      <StepHeader
        eyebrow="A little more context"
        title="Help us get it right."
        subtitle={`We’ll ask up to ${session.question_limit} focused questions to understand your intent. Answer what you can, skip anything undecided, or let us make assumptions for the rest.`}
      />
      {history.length ? (
        <div className="question-history">
          <button type="button" className="history-toggle" onClick={() => setHistoryOpen((open) => !open)} aria-expanded={historyOpen}>
            <span>Previous answers <span className="history-count">{history.length}</span></span>
            <Icon name="chevron" size={16} />
          </button>
          {historyOpen ? <div className="history-answers">{history.map((item, index) => <div key={`${item.question}-${index}`} className="history-answer"><span className="history-check">{item.skipped ? "—" : "✓"}</span><div><strong>{item.question}</strong><span>{item.skipped ? "Skipped for now" : item.answer}</span><small>{item.skipped ? "Unresolved" : "Confirmed by you"}</small></div></div>)}</div> : null}
        </div>
      ) : null}
      <form onSubmit={submitAnswer} className="question-list">
        <div className="question-card active-question">
          <div className="question-meta"><span>Question {session.question_count + 1} of up to {session.question_limit}</span><span>{Math.round((session.question_count / session.question_limit) * 100)}% complete</span></div>
          <div className="question-copy"><span className="question-number">{session.question_count + 1}.</span><strong>{session.current_question}</strong><textarea value={answer} onChange={(event) => setAnswer(event.target.value)} placeholder="Type your answer here..." rows={4} autoFocus /></div>
        </div>
        <div className="question-actions">
          <BackButton onClick={onBack} disabled={isPending} />
          <div className="question-secondary-actions">
            <button type="button" className="text-action" onClick={(event) => submitAnswer(event, true)} disabled={isPending}>Skip for now</button>
            <button type="button" className="assumption-action" onClick={() => assumptionsMutation.mutate()} disabled={isPending}>Make assumptions</button>
          </div>
          <button disabled={isPending || !answer.trim()} className="button button-dark">{answerMutation.isPending ? <Spinner label="Saving..." /> : <>Continue <Icon name="arrow" size={16} /></>}</button>
        </div>
        <ErrorMessage error={answerMutation.error || assumptionsMutation.error} onRetry={() => (answerMutation.error ? answerMutation.mutate(answer.trim() ? { answer: answer.trim() } : { skipped: true }) : assumptionsMutation.mutate())} />
      </form>
    </div>
  );
}

function CustomRequirementsScreen({ session, onDone, onBack }) {
  const [value, setValue] = useState(""); const [validationError, setValidationError] = useState("");
  const mutation = useMutation({ mutationFn: (customRequirements) => request(`/api/sessions/${session.id}/custom-requirements/`, { method: "PATCH", body: JSON.stringify({ custom_requirements: customRequirements }) }), onSuccess: onDone });
  const submit = (event) => { event.preventDefault(); if (value.length > maxInputLength) { setValidationError(`Please keep custom requirements under ${maxInputLength} characters.`); return; } setValidationError(""); mutation.mutate(value); };
  return <div className="flow-container"><WizardProgress current={2} /><StepHeader eyebrow="Your perspective" title="Anything else to add?" subtitle="Add preferences, constraints, or context that should guide the final prompt. This is optional." /><form onSubmit={submit} className="prompt-form"><div className="textarea-wrap"><textarea value={value} onChange={(event) => setValue(event.target.value)} rows={8} placeholder="For example: Keep the tone friendly and make the solution easy for a small team to maintain..." /><span className="textarea-count">{value.length}/{maxInputLength}</span></div>{validationError ? <p className="field-error">{validationError}</p> : null}<div className="form-footer"><BackButton onClick={onBack} disabled={mutation.isPending} /><button disabled={mutation.isPending} className="button button-dark">{mutation.isPending ? <Spinner label="Organizing..." /> : <>Review specification <Icon name="arrow" size={16} /></>}</button></div><ErrorMessage error={mutation.error} onRetry={() => mutation.mutate(mutation.variables)} /></form></div>;
}

function ReviewScreen({ session, onDone, onBack, onReset, generationMutation }) {
  const [spec, setSpec] = useState(session.specification);
  const [confirmedOpen, setConfirmedOpen] = useState(false);
  const mutation = useMutation({ mutationFn: () => request(`/api/sessions/${session.id}/spec/`, { method: "PATCH", body: JSON.stringify(spec) }), onSuccess: onDone });
  const updateList = (field, index, value) => setSpec((current) => ({ ...current, [field]: current[field].map((item, i) => i === index ? value : item), ...(field === "assumptions" ? { assumption_provenance: (current.assumption_provenance || []).map((item, i) => i === index ? { ...item, text: value } : item) } : {}) }));
  const removeListItem = (field, index) => setSpec((current) => ({ ...current, [field]: current[field].filter((_, i) => i !== index), ...(field === "assumptions" ? { assumption_provenance: (current.assumption_provenance || []).filter((_, i) => i !== index) } : {}) }));
  return <div className="flow-container review-flow"><WizardProgress current={3} /><StepHeader eyebrow="Final check" title="Make it yours." subtitle="Review the direction below. You have the final say before we write your prompt." /><form onSubmit={(event) => { event.preventDefault(); mutation.mutate(); }} className="review-form"><section className="review-goal"><span className="field-heading">Goal</span><p className="goal-value">{spec.goal}</p></section><div className="review-section-label">AI interpretation <span>Editable structure inferred from your idea and answers</span></div><div className="spec-grid">{listFields.map((field) => <fieldset key={field} className="spec-card"><div className="spec-card-heading"><span>{field === "assumptions" ? "Assumptions to review" : field}</span>{field === "assumptions" ? <span className="provenance-badge">AI-generated</span> : null}<span className="spec-count">{spec[field].length}</span></div>{spec[field].length ? spec[field].map((item, index) => <div key={`${field}-${index}`} className="spec-item"><div className="spec-item-content"><input className={item === "" ? "new-spec-input" : ""} value={item} placeholder="Add an item..." onChange={(event) => updateList(field, index, event.target.value)} />{field === "assumptions" ? <span className="item-provenance">{spec.assumption_provenance?.[index]?.source === "ai_analysis" ? "From initial analysis" : spec.assumption_provenance?.[index]?.source === "user_added" ? "Added by you" : "Added after clarification"}</span> : null}</div><button type="button" onClick={() => removeListItem(field, index)} aria-label={`Remove ${field} item`}>×</button></div>) : <p className="spec-empty">No {field} specified yet.</p>}<button type="button" onClick={() => setSpec({ ...spec, [field]: [...spec[field], ""], assumption_provenance: field === "assumptions" ? [...(spec.assumption_provenance || []), { text: "", source: "user_added" }] : spec.assumption_provenance })} className="add-item"><Icon name="plus" size={14} /> Add item</button></fieldset>)}</div><fieldset className="answers-card confirmed-card"><button type="button" className="confirmed-heading" onClick={() => setConfirmedOpen((open) => !open)} aria-expanded={confirmedOpen}><span><strong>Confirmed decisions</strong><small>{spec.answers.filter((item) => item.answer?.trim()).length} confirmed · {spec.answers.filter((item) => item.skipped).length} skipped</small></span><Icon name="chevron" size={16} /></button>{confirmedOpen ? <div className="confirmed-list">{spec.answers.length ? spec.answers.map((item, index) => <div key={item.question} className="answer-row"><div><strong>{item.question}</strong><span className={item.skipped ? "answer-provenance skipped" : "answer-provenance"}>{item.skipped ? "Skipped — unresolved" : "Confirmed by you"}</span><input className="answer-input" value={item.answer || ""} onChange={(event) => setSpec({ ...spec, answers: spec.answers.map((answer, answerIndex) => answerIndex === index ? { ...answer, answer: event.target.value, skipped: false, provenance: "confirmed" } : answer) })} placeholder="Skipped — click to provide an answer" /></div></div>) : <p className="muted-copy">No clarification decisions yet.</p>}</div> : null}</fieldset><div className="form-footer"><div className="review-actions-left"><BackButton onClick={onBack} disabled={mutation.isPending || generationMutation.isPending} /><button type="button" className="review-start-over" onClick={onReset} disabled={mutation.isPending || generationMutation.isPending}>Start over</button></div><span className="privacy-note">You can edit everything except the original goal.</span><button disabled={mutation.isPending || generationMutation.isPending} className="button button-dark">{mutation.isPending ? <Spinner label="Saving..." /> : generationMutation.isPending ? <Spinner label="Writing your prompt..." /> : <>Generate prompt <Icon name="arrow" size={16} /> </>}</button></div><ErrorMessage error={mutation.error} onRetry={() => mutation.mutate()} /><ErrorMessage error={generationMutation.error} onRetry={() => generationMutation.mutate()} /></form></div>;
}

function ResultScreen({ session, onBack, onReset }) {
  const [copied, setCopied] = useState(false); const content = session.generated_prompt?.content || "";
  const copy = async () => { await navigator.clipboard.writeText(content); setCopied(true); setTimeout(() => setCopied(false), 2200); };
  const download = () => { const url = URL.createObjectURL(new Blob([content], { type: "text/markdown;charset=utf-8" })); const link = document.createElement("a"); link.href = url; link.download = "prompt.md"; link.click(); URL.revokeObjectURL(url); };
  return <div className="result-container"><WizardProgress current={4} /><div className="result-hero"><span className="success-badge"><Icon name="check" size={15} /> Ready to use</span><h1>Your prompt is ready.</h1><p>Clear direction, shaped from your original idea.</p></div><div className="output-card"><div className="output-header"><span><span className="output-dot" /> Markdown prompt</span><span className="output-label">Generated for {session.target_category}</span></div><pre>{content}</pre><div className="output-actions"><button onClick={copy} className="button button-dark button-small">{copied ? <><Icon name="check" size={15} /> Copied!</> : <><Icon name="copy" size={15} /> Copy prompt</>}</button><button onClick={download} className="button button-outline button-small"><Icon name="download" size={15} /> Download .md</button></div></div><div className="result-navigation"><BackButton onClick={onBack} /><button type="button" onClick={onReset} className="start-another"><Icon name="plus" size={16} /> Start another prompt</button></div></div>;
}

function SessionFlow({ sessionId, onReset }) {
  const queryClient = useQueryClient();
  const { data: session, isLoading, error } = useQuery({ queryKey: ["session", sessionId], queryFn: () => request(`/api/sessions/${sessionId}/`), refetchOnWindowFocus: false, retry: false });
  const refresh = (nextSession) => queryClient.setQueryData(["session", sessionId], nextSession);
  const generate = useMutation({ mutationFn: () => request(`/api/sessions/${sessionId}/generate/`, { method: "POST" }), onSuccess: refresh });
  const goBack = useMutation({ mutationFn: () => request(`/api/sessions/${sessionId}/back/`, { method: "POST" }), onSuccess: refresh });
  if (isLoading) return <LoadingState label="Loading your workspace..." />;
  if (error) return <div className="state-card"><div className="empty-history"><div className="empty-icon"><Icon name="clock" size={25} /></div><h2>This prompt is no longer available.</h2><p>Your saved session may have expired or been cleared. Start a new prompt to continue.</p><button onClick={onReset} className="button button-dark">Start a new prompt <Icon name="arrow" size={16} /></button><ErrorMessage error={error} onRetry={() => queryClient.invalidateQueries({ queryKey: ["session", sessionId] })} /></div></div>;
  if (session.status === "awaiting_answers") return <QuestionsScreen session={session} onDone={refresh} onBack={onReset} />;
  if (session.status === "awaiting_custom_reqs") return <CustomRequirementsScreen session={session} onDone={refresh} onBack={() => session.specification.unknowns.length ? goBack.mutate() : onReset()} />;
  if (session.status === "ready_for_review") return <ReviewScreen session={session} onDone={() => generate.mutate()} onBack={() => goBack.mutate()} onReset={onReset} generationMutation={generate} />;
  if (session.status === "complete") return <ResultScreen session={session} onBack={() => goBack.mutate()} onReset={onReset} />;
  if (session.status === "analyzing") return <LoadingState label="Analyzing your idea..." detail="Finding the right structure and asking only what matters." />;
  if (session.status === "generating_assumptions") return <LoadingState label="Filling in the remaining details..." detail="Using your answers first, then making only the assumptions you can review." />;
  if (session.status === "generating") return <LoadingState label="Writing your prompt..." detail="Turning your confirmed direction into something you can use." />;
  return <div className="state-card"><ErrorMessage error={generate.error || new Error("This session needs attention.")} onRetry={() => generate.mutate()} /><button onClick={onReset} className="start-another">Start over</button></div>;
}

function LoadingState({ label, detail }) {
  return <div className="loading-state"><div className="loading-orbit"><span /><span /><span /></div><h2>{label}</h2><p>{detail || "One moment while we bring your workspace together."}</p><div className="loading-bar"><span /></div></div>;
}

function SessionsList() {
  const queryClient = useQueryClient();
  const { data, isLoading, error } = useQuery({ queryKey: ["sessions"], queryFn: () => request("/api/sessions/") });
  if (isLoading) return <LoadingState label="Loading your history..." />;
  if (error) return <div className="state-card"><ErrorMessage error={error} onRetry={() => queryClient.invalidateQueries({ queryKey: ["sessions"] })} /></div>;
  return <div className="history-page"><StepHeader eyebrow="Workspace" title="Your prompt history." subtitle="A quiet place for the ideas you've already shaped." />{!data.length ? <div className="empty-history"><div className="empty-icon"><Icon name="clock" size={25} /></div><h2>No saved prompts yet.</h2><p>Start with a rough idea and we’ll help you give it direction.</p><Link to="/" className="button button-dark">Create your first prompt <Icon name="arrow" size={16} /></Link></div> : <div className="session-cards">{data.map((session) => <Link key={session.id} to={`/sessions/${session.id}`} className="session-card"><div className="session-card-top"><span className="session-category">{session.target_category}</span><span className="session-date">{new Date(session.created_at).toLocaleDateString()}</span></div><h3>{session.raw_input}</h3><div className="session-card-bottom"><span className="status-pill">{session.status.replaceAll("_", " ")}</span><span className="session-open">Open <Icon name="arrow" size={14} /></span></div></Link>)}</div>}</div>;
}

function SessionDetail() {
  const { sessionId } = useParams();
  const { data: session, isLoading, error } = useQuery({ queryKey: ["session", sessionId], queryFn: () => request(`/api/sessions/${sessionId}/`), retry: false });
  if (isLoading) return <LoadingState label="Loading your prompt..." />;
  if (error) return <div className="state-card"><ErrorMessage error={error} /></div>;
  if (session.status !== "complete") return <SessionFlow sessionId={sessionId} onReset={() => {}} />;
  return <ResultScreen session={session} />;
}

function InfoPage({ title, intro, sections }) {
  return <div className="placeholder-page info-page"><span className="eyebrow"><span className="eyebrow-dot" /> Prompt Architect</span><h1>{title}</h1><p>{intro}</p>{sections.map(({ heading, body }) => <section key={heading}><h2>{heading}</h2><p>{body}</p></section>)}<Link to="/" className="button button-dark">Back to Prompt Architect <Icon name="arrow" size={16} /></Link></div>;
}

function App() {
  const [sessionId, setSessionId] = useState(() => localStorage.getItem(sessionStorageKey));
  const [authSession, setAuthSession] = useState(null);
  const location = useLocation(); const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: sessions, isLoading: sessionsLoading } = useQuery({ queryKey: ["sessions"], queryFn: () => request("/api/sessions/"), enabled: Boolean(authSession), retry: false });
  const setSession = (session) => {
    localStorage.setItem(sessionStorageKey, session.id);
    if (session.session_token) localStorage.setItem(sessionTokenStorageKey, session.session_token);
    else localStorage.removeItem(sessionTokenStorageKey);
    setSessionId(session.id);
  };
  const reset = () => {
    localStorage.removeItem(sessionStorageKey);
    localStorage.removeItem(sessionTokenStorageKey);
    setSessionId(null);
  };
  useEffect(() => { if (!supabase) return undefined; supabase.auth.getSession().then(({ data }) => setAuthSession(data.session)); const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => setAuthSession(session)); return () => listener.subscription.unsubscribe(); }, []);
  const logout = async () => { await supabase?.auth.signOut(); queryClient.removeQueries({ queryKey: ["sessions"] }); navigate("/"); };
  let content;
  if (location.pathname === "/login") content = <AuthScreen mode="login" onAuthenticated={() => navigate("/")} />;
  else if (location.pathname === "/signup") content = <AuthScreen mode="signup" onAuthenticated={() => navigate("/")} />;
  else if (location.pathname === "/docs") content = <InfoPage title="Documentation" intro="Prompt Architect turns an idea into a structured, implementation-ready prompt." sections={[
    { heading: "How it works", body: "Enter an idea, answer clarification questions or ask Prompt Architect to make bounded assumptions, review the interpretation, and generate the final prompt." },
    { heading: "Your data", body: "Sessions are stored by the backend so you can resume them. Sign-in attaches sessions to your account; anonymous sessions are protected by a private browser possession token." },
    { heading: "Production setup", body: "Configure the backend environment from backend/.env.example, run Django migrations, serve Django behind HTTPS, and set VITE_API_BASE_URL plus the public Supabase values in the frontend environment." },
  ]} />;
  else if (location.pathname === "/privacy") content = <InfoPage title="Privacy Policy" intro="This summary explains what Prompt Architect processes. Review it before entering confidential information." sections={[
    { heading: "Information processed", body: "We process your prompt idea, clarification answers, structured specification, generated prompt, timestamps, and—when you sign in—your Supabase user ID and email address." },
    { heading: "Gemini processing", body: "Your idea and answers are sent from our backend to Google Gemini to analyze requirements and generate prompts. Do not submit passwords, API keys, regulated data, or confidential information you are not permitted to share." },
    { heading: "Retention and deletion", body: "Saved sessions remain available until deleted by the application owner. Production deployments should provide a deletion workflow and retention schedule before collecting sensitive or regulated data." },
  ]} />;
  else if (location.pathname === "/terms") content = <InfoPage title="Terms" intro="Use Prompt Architect responsibly and review generated output before relying on it." sections={[
    { heading: "No guarantee of output", body: "Generated prompts and assumptions are suggestions, not professional, legal, security, or implementation advice. You are responsible for reviewing and validating them." },
    { heading: "Acceptable use", body: "Do not use the service to submit secrets, personal data you do not have permission to process, or content that abuses the service or attempts to evade its safeguards." },
  ]} />;
  else if (location.pathname === "/security") content = <InfoPage title="Security" intro="Prompt Architect keeps Gemini credentials on the backend and uses Supabase Auth for browser authentication." sections={[
    { heading: "Credentials", body: "Gemini API keys, database credentials, and Supabase service-level credentials must never be placed in frontend code or VITE_ variables. Public environment examples contain placeholders only." },
    { heading: "Reporting an issue", body: "Please do not publish sensitive security details in a public issue. Contact the project maintainer privately with reproduction steps and affected endpoints." },
    { heading: "Deployment baseline", body: "Use HTTPS, restrictive CORS and ALLOWED_HOSTS values, secure cookies, a strong Django secret, enforced JWT issuer validation, database backups, and monitoring." },
  ]} />;
  else if (location.pathname === "/faqs") content = <InfoPage title="FAQs" intro="A few practical answers about the current MVP." sections={[
    { heading: "How many questions will I get?", body: "The backend chooses category-specific limits: up to 8 for General and Design, and up to 10 for Frontend, Backend, and Full Stack. You can stop early and ask the system to make assumptions." },
    { heading: "Can I edit the result?", body: "Yes. Review screens preserve confirmed answers, skipped items, and assumption provenance so you can correct the specification before generating." },
    { heading: "Is my anonymous idea public?", body: "No. Anonymous sessions use a private possession token stored by the browser. Keep that browser storage private; clearing it means the session cannot be recovered." },
  ]} />;
  else if (location.pathname === "/sessions") content = authSession ? <SessionsList /> : <AuthScreen mode="login" onAuthenticated={() => navigate("/sessions")} />;
  else if (location.pathname.startsWith("/sessions/")) content = <SessionDetail />;
  else content = sessionId ? <SessionFlow sessionId={sessionId} onReset={reset} /> : <InputScreen onCreated={setSession} />;
  return <AppShell authSession={authSession} sessions={sessions} sessionsLoading={sessionsLoading} onLogout={logout}>{content}</AppShell>;
}

export default App;
