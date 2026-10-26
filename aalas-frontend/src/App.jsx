import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ArrowDownToLine, ArrowLeft, ArrowRight, ArrowUpRight, Bell, BriefcaseBusiness,
  Building2, CalendarDays, Check, CheckCircle2, ChevronDown, ChevronRight, CircleHelp,
  Clock3, Code2, FileBadge, FileCheck2, FileCode2, FileText, Filter, GraduationCap,
  LoaderCircle, LogOut, MapPin, Menu, RefreshCw, Search, Settings2, Sparkles, Upload,
  UserRound, UsersRound, X, Zap, AlertCircle, ExternalLink, SlidersHorizontal,
} from 'lucide-react';

const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
const ACTIVE_PROFILE_KEY = 'aalas.activeProfileId';
const JOB_LIMIT = 50;

async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, options);
  const contentType = response.headers.get('content-type') || '';
  const body = contentType.includes('application/json')
    ? await response.json().catch(() => ({}))
    : await response.text().catch(() => '');
  if (!response.ok) {
    const detail = typeof body === 'object' ? body.detail || body.message : body;
    throw new Error(detail || `Request failed (${response.status})`);
  }
  return body;
}

async function downloadFile(path, fallbackName) {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    let detail = `Download failed (${response.status})`;
    try { const data = await response.json(); detail = data.detail || detail; } catch { /* no JSON body */ }
    throw new Error(detail);
  }
  const blob = await response.blob();
  const disposition = response.headers.get('content-disposition') || '';
  const match = disposition.match(/filename\*?=(?:UTF-8''|\")?([^\";]+)/i);
  const filename = match ? decodeURIComponent(match[1].replace(/"/g, '')) : fallbackName;
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1500);
}

const moneyLabel = (amount, currency = 'INR') => {
  if (amount === null || amount === undefined || amount === '') return '';
  try { return new Intl.NumberFormat('en-IN', { style: 'currency', currency, maximumFractionDigits: 0 }).format(amount); }
  catch { return `${currency} ${amount}`; }
};

function formatDate(value) {
  if (!value) return 'Date not listed';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }).format(date);
}

function initials(value = '') {
  return value.split(/\s+/).filter(Boolean).slice(0, 2).map((word) => word[0].toUpperCase()).join('') || 'J';
}

function Spinner({ small = false }) {
  return <LoaderCircle className={`spin ${small ? 'spin-small' : ''}`} size={small ? 15 : 18} />;
}

function Button({ children, variant = 'primary', size = '', loading = false, disabled = false, block = false, className = '', ...props }) {
  return (
    <button className={`btn btn-${variant} ${size ? `btn-${size}` : ''} ${block ? 'btn-block' : ''} ${className}`} disabled={disabled || loading} {...props}>
      {loading ? <Spinner small /> : null}{children}
    </button>
  );
}

function Toast({ toast, onClose }) {
  useEffect(() => {
    if (!toast) return undefined;
    const timer = window.setTimeout(onClose, 5200);
    return () => window.clearTimeout(timer);
  }, [toast, onClose]);
  if (!toast) return null;
  return <div className={`toast toast-${toast.type || 'info'}`} role="status">
    {toast.type === 'error' ? <AlertCircle size={18} /> : <CheckCircle2 size={18} />}
    <span>{toast.message}</span><button onClick={onClose} aria-label="Dismiss notification"><X size={16} /></button>
  </div>;
}

function Registration({ onCreated, setToast }) {
  const [step, setStep] = useState(1);
  const [busy, setBusy] = useState(false);
  const [resume, setResume] = useState(null);
  const [restoreId, setRestoreId] = useState('');
  const [restoring, setRestoring] = useState(false);
  const fileRef = useRef(null);
  const [form, setForm] = useState({
    name: '', email: '', target_roles: 'Software Engineer, Backend Engineer', locations: 'Bengaluru, Hyderabad',
    job_type: 'full time', salary_min: '', salary_currency: 'INR', experience_level: 'entry level', additional_context: '',
  });
  const update = (key, value) => setForm((current) => ({ ...current, [key]: value }));

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    try {
      const payload = {
        ...form,
        salary_min: form.salary_min.trim() === '' ? null : Number(form.salary_min),
      };
      delete payload.resume_latex;
      const user = await apiRequest('/api/users', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      if (resume) {
        const multipart = new FormData();
        multipart.append('file', resume);
        await apiRequest(`/api/users/${user.id}/resume`, { method: 'POST', body: multipart });
      }
      localStorage.setItem(ACTIVE_PROFILE_KEY, String(user.id));
      onCreated(user);
      setToast({ type: 'success', message: resume ? 'Profile created and resume uploaded.' : 'Profile created. Upload your .tex resume from the profile page to unlock document generation.' });
    } catch (error) {
      setToast({ type: 'error', message: error.message });
    } finally { setBusy(false); }
  }

  async function restore(event) {
    event.preventDefault();
    const id = Number(restoreId);
    if (!Number.isInteger(id) || id < 1) { setToast({ type: 'error', message: 'Enter a valid profile ID.' }); return; }
    setRestoring(true);
    try {
      const user = await apiRequest(`/api/users/${id}`);
      localStorage.setItem(ACTIVE_PROFILE_KEY, String(user.id));
      onCreated(user);
      setToast({ type: 'success', message: `Welcome back, ${user.name}.` });
    } catch (error) { setToast({ type: 'error', message: error.message }); }
    finally { setRestoring(false); }
  }

  return <div className="onboarding-shell">
    <div className="onboarding-left">
      <div className="brand brand-light"><div className="brand-mark"><span>a</span></div><span>aalas<span className="brand-dot">.</span></span></div>
      <div className="onboarding-copy">
        <span className="eyebrow eyebrow-light"><Sparkles size={14} /> Your job search, on autopilot</span>
        <h1>Less scrolling.<br />More <em>shortlisting.</em></h1>
        <p>Tell Aalas what you're looking for. We'll find relevant openings and help you prepare a sharper application for each one.</p>
        <div className="onboarding-points">
          <div><span><Search size={17} /></span><div><b>Relevant jobs, ranked</b><small>Hybrid keyword and semantic search</small></div></div>
          <div><span><FileCode2 size={17} /></span><div><b>Your resume, tailored</b><small>Keep your own LaTeX template</small></div></div>
          <div><span><Zap size={17} /></span><div><b>Fewer repetitive tasks</b><small>Cover letters on demand</small></div></div>
        </div>
      </div>
      <div className="onboarding-foot"><span>Built for the slow-and-steady job hunt.</span><span>Hacktoberfest 2026 · Week 3</span></div>
    </div>
    <div className="onboarding-right">
      <div className="form-wrap">
        <div className="mobile-brand brand"><div className="brand-mark"><span>a</span></div><span>aalas<span className="brand-dot">.</span></span></div>
        <div className="form-heading"><span className="step-tag">GET STARTED · 0{step} / 02</span><h2>{step === 1 ? 'Let’s set up your profile.' : 'Fine-tune your search.'}</h2><p>{step === 1 ? 'First, tell us a little about you.' : 'These preferences help us find your best-fit openings.'}</p></div>
        <form onSubmit={step === 1 ? (e) => { e.preventDefault(); setStep(2); } : submit}>
          {step === 1 ? <>
            <div className="form-grid">
              <label className="field"><span>Full name</span><input required value={form.name} onChange={(e) => update('name', e.target.value)} placeholder="Your name" autoComplete="name" /></label>
              <label className="field"><span>Email address</span><input type="email" required value={form.email} onChange={(e) => update('email', e.target.value)} placeholder="you@example.com" autoComplete="email" /></label>
            </div>
            <label className="field"><span>Target job titles <small>Separate multiple roles with commas</small></span><input required value={form.target_roles} onChange={(e) => update('target_roles', e.target.value)} placeholder="Software Engineer, Data Analyst" /></label>
            <label className="field"><span>Additional experience <small>Projects or skills not in your resume</small></span><textarea value={form.additional_context} onChange={(e) => update('additional_context', e.target.value)} rows={3} placeholder="Built a project using FastAPI and PostgreSQL…" /></label>
          </> : <>
            <label className="field"><span>Preferred locations <small>Comma-separated cities or regions</small></span><input required value={form.locations} onChange={(e) => update('locations', e.target.value)} placeholder="Bengaluru, Remote" /></label>
            <div className="form-grid">
              <label className="field"><span>Job type</span><select value={form.job_type} onChange={(e) => update('job_type', e.target.value)}><option value="full time">Full-time</option><option value="part time">Part-time</option><option value="contract">Contract</option><option value="temporary">Temporary</option><option value="internship">Internship</option></select></label>
              <label className="field"><span>Experience level</span><select value={form.experience_level} onChange={(e) => update('experience_level', e.target.value)}><option value="internship">Internship</option><option value="entry level">Entry level</option><option value="associate">Associate</option><option value="senior">Senior</option><option value="director">Director</option><option value="executive">Executive</option></select></label>
            </div>
            <div className="form-grid salary-grid">
              <label className="field"><span>Minimum salary <small>Optional annual amount</small></span><input inputMode="numeric" type="number" min="0" value={form.salary_min} onChange={(e) => update('salary_min', e.target.value)} placeholder="e.g. 1200000" /></label>
              <label className="field"><span>Currency</span><select value={form.salary_currency} onChange={(e) => update('salary_currency', e.target.value)}><option value="INR">INR · Indian Rupee</option><option value="USD">USD · US Dollar</option><option value="EUR">EUR · Euro</option><option value="GBP">GBP · Pound</option></select></label>
            </div>
            <div className="upload-zone compact-upload" onClick={() => fileRef.current?.click()} role="button" tabIndex={0} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') fileRef.current?.click(); }}>
              <div className="upload-symbol"><Upload size={19} /></div><div className="upload-text"><b>{resume ? resume.name : 'Upload your LaTeX resume'}</b><span>{resume ? `${(resume.size / 1024).toFixed(0)} KB · ready to upload` : 'A .tex file, up to 1 MB. You can upload it later.'}</span></div><span className="upload-action">{resume ? 'Change' : 'Browse'}</span>
              <input ref={fileRef} type="file" accept=".tex,text/plain" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f && !f.name.toLowerCase().endsWith('.tex')) { setToast({ type: 'error', message: 'Please select a .tex file.' }); e.target.value = ''; return; } if (f && f.size > 1024 * 1024) { setToast({ type: 'error', message: 'Resume must be 1 MB or smaller.' }); e.target.value = ''; return; } setResume(f || null); }} />
            </div>
            <p className="form-note"><CircleHelp size={14} /> Salary is a preference, not a strict filter. Jobs without listed salary remain eligible.</p>
          </>}
          <div className="form-actions">
            {step === 2 && <Button type="button" variant="ghost" onClick={() => setStep(1)}><ArrowLeft size={16} /> Back</Button>}
            <Button type="submit" loading={busy} className="form-next">{step === 1 ? <>Continue <ArrowRight size={16} /></> : <>Create my profile <ArrowRight size={16} /></>}</Button>
          </div>
        </form>
        <div className="restore-card"><span>Already have a profile ID?</span><form className="restore-form" onSubmit={restore}><input aria-label="Profile ID" inputMode="numeric" value={restoreId} onChange={(e) => setRestoreId(e.target.value)} placeholder="Enter profile ID" /><Button type="submit" variant="outline" loading={restoring}>Restore</Button></form><small>This restores a saved profile on this backend. Authentication is not enabled yet.</small></div>
      </div>
    </div>
  </div>;
}

function Sidebar({ activeView, setActiveView, user, onReset }) {
  return <aside className="sidebar">
    <div className="brand"><div className="brand-mark"><span>a</span></div><span>aalas<span className="brand-dot">.</span></span></div>
    <div className="workspace-label">WORKSPACE</div>
    <nav className="side-nav" aria-label="Main navigation">
      <button className={activeView === 'jobs' ? 'active' : ''} onClick={() => setActiveView('jobs')}><BriefcaseBusiness size={18} /> Job board <span className="nav-pill">AI</span></button>
      <button className={activeView === 'profile' ? 'active' : ''} onClick={() => setActiveView('profile')}><UserRound size={18} /> My profile</button>
    </nav>
    <div className="sidebar-spacer" />
    <div className="sidebar-tip"><div className="tip-icon"><Sparkles size={16} /></div><b>Small steps add up.</b><p>Fresh jobs, a focused resume, and one good application at a time.</p><span className="tip-progress"><i /></span><small>Your job hunt, simplified</small></div>
    <div className="side-user"><div className="avatar">{initials(user.name)}</div><div className="side-user-meta"><b>{user.name}</b><span>Profile #{user.id}</span></div><button className="icon-button" title="End this browser session" onClick={onReset}><LogOut size={16} /></button></div>
  </aside>;
}

function Topbar({ user, activeView, setToast, setMobileNav }) {
  return <header className="topbar">
    <div className="topbar-left"><button className="mobile-menu icon-button" aria-label="Open navigation" onClick={setMobileNav}><Menu size={19} /></button><div className="breadcrumb">Workspace <ChevronRight size={14} /> <b>{activeView === 'jobs' ? 'Job board' : 'My profile'}</b></div></div>
    <div className="topbar-right"><span className="connection-status"><i /> API configured</span><a href={`${API_BASE}/docs`} target="_blank" rel="noreferrer" className="top-help"><CircleHelp size={16} /> API docs <ExternalLink size={12} /></a><div className="avatar avatar-small">{initials(user.name)}</div></div>
  </header>;
}

function JobCard({ job, selected, onSelect, index }) {
  const score = Number(job.relevance_score);
  return <button className={`job-card ${selected ? 'job-card-selected' : ''}`} onClick={() => onSelect(job)}>
    <div className="job-card-main">
      <div className="company-logo-wrap">{job.company_logo ? <img src={job.company_logo} alt={`${job.company} logo`} loading="lazy" onError={(e) => { e.currentTarget.style.display = 'none'; }} /> : <span>{initials(job.company)}</span>}</div>
      <div className="job-title-area"><h3>{job.position}</h3><div className="company-line"><b>{job.company || 'Company not listed'}</b><span className="dot-separator">·</span><span>{job.location || 'Location not listed'}</span></div><div className="job-tags"><span><Clock3 size={13} /> {job.ago_time || (job.posted_date ? formatDate(job.posted_date) : 'Recently listed')}</span><span><BriefcaseBusiness size={13} /> {job.salary_text && job.salary_text !== 'Not specified' ? job.salary_text : 'Salary not specified'}</span></div></div>
      <div className="job-card-right">{Number.isFinite(score) && <div className="match-score"><Sparkles size={12} /> <span>{score.toFixed(4)}</span><small>RRF score</small></div>}<ChevronRight size={17} className="job-chevron" /></div>
    </div>
    {job.description && <p className="job-summary">{job.description.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 190)}{job.description.length > 190 ? '…' : ''}</p>}
  </button>;
}

function JobDetails({ job, user, onClose, onToast, resumeReady }) {
  const [activeDoc, setActiveDoc] = useState('');
  const [busy, setBusy] = useState('');
  const [resumeResult, setResumeResult] = useState(null);
  const [coverResult, setCoverResult] = useState(null);
  const [pdfObjectUrl, setPdfObjectUrl] = useState('');
  const [showDescription, setShowDescription] = useState(true);
  const detailRef = useRef(null);

  useEffect(() => () => { if (pdfObjectUrl) URL.revokeObjectURL(pdfObjectUrl); }, [pdfObjectUrl]);

  async function generateResume() {
    if (!resumeReady) { onToast({ type: 'error', message: 'Upload your .tex resume from My profile before tailoring.' }); return; }
    setBusy('resume'); setActiveDoc('resume'); setResumeResult(null);
    try {
      const result = await apiRequest('/api/documents/tailor-resume', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ user_id: user.id, job_id: job.id }) });
      setResumeResult(result);
      try {
        const response = await fetch(`${API_BASE}${result.pdf_url}`);
        if (response.ok) {
          const blobUrl = URL.createObjectURL(await response.blob());
          setPdfObjectUrl((old) => { if (old) URL.revokeObjectURL(old); return blobUrl; });
        }
      } catch { /* the download button can fetch the PDF again */ }
      onToast({ type: 'success', message: 'Tailored resume generated.' });
    } catch (error) { onToast({ type: 'error', message: error.message }); setActiveDoc(''); }
    finally { setBusy(''); }
  }

  async function generateCover() {
    if (!resumeReady) { onToast({ type: 'error', message: 'Upload your .tex resume from My profile before generating a cover letter.' }); return; }
    setBusy('cover'); setActiveDoc('cover'); setCoverResult(null);
    try {
      const result = await apiRequest('/api/documents/cover-letter', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ user_id: user.id, job_id: job.id }) });
      setCoverResult(result);
      onToast({ type: 'success', message: 'Cover letter generated.' });
    } catch (error) { onToast({ type: 'error', message: error.message }); setActiveDoc(''); }
    finally { setBusy(''); }
  }

  async function downloadResumePdf() {
    if (!resumeResult?.pdf_url) return;
    try { await downloadFile(resumeResult.pdf_url, 'aalas-tailored-resume.pdf'); }
    catch (error) { onToast({ type: 'error', message: error.message }); }
  }
  async function downloadCover() {
    if (!coverResult?.download_url) return;
    try { await downloadFile(coverResult.download_url, 'aalas-cover-letter.txt'); }
    catch (error) { onToast({ type: 'error', message: error.message }); }
  }
  function downloadLatex() {
    if (!resumeResult?.latex) return;
    const blobUrl = URL.createObjectURL(new Blob([resumeResult.latex], { type: 'application/x-tex;charset=utf-8' }));
    const anchor = document.createElement('a'); anchor.href = blobUrl; anchor.download = 'tailored-resume.tex'; anchor.click(); URL.revokeObjectURL(blobUrl);
  }

  const description = job.description?.replace(/<\/?(p|div|br|li|ul|ol|strong|b|h[1-6])\b[^>]*>/gi, ' ').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/\s+/g, ' ').trim();
  return <div className="detail-backdrop" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
    <section className="job-detail-panel" role="dialog" aria-modal="true" aria-label={`Details for ${job.position}`} ref={detailRef}>
      <div className="detail-topbar"><span className="detail-eyebrow"><span className="live-dot" /> JOB DETAILS</span><button className="icon-button close-button" aria-label="Close details" onClick={onClose}><X size={19} /></button></div>
      <div className="detail-heading">
        <div className="detail-company-logo">{job.company_logo ? <img src={job.company_logo} alt="" /> : initials(job.company)}</div>
        <h2>{job.position}</h2><div className="detail-company">{job.company} <span>·</span> {job.location}</div>
        <div className="detail-meta"><span><MapPin size={14} /> {job.location || 'Location not listed'}</span><span><CalendarDays size={14} /> {job.ago_time || formatDate(job.posted_date)}</span></div>
        <div className="detail-salary"><span className="salary-mark">₹</span><div><b>{job.salary_text || 'Salary not specified'}</b><small>{job.salary_text === 'Not specified' || !job.salary_text ? 'The listing does not disclose salary' : 'As shown on the job listing'}</small></div></div>
      </div>
      <div className="detail-actions">
        <Button onClick={generateResume} loading={busy === 'resume'} disabled={Boolean(busy)}><Sparkles size={16} /> Tailor resume</Button>
        <Button variant="outline" onClick={generateCover} loading={busy === 'cover'} disabled={Boolean(busy)}><FileText size={16} /> Cover letter</Button>
        <a className="btn btn-ghost btn-icon-link" href={job.job_url} target="_blank" rel="noreferrer" title="Open original job posting"><ArrowUpRight size={17} /></a>
      </div>
      {!resumeReady && <div className="inline-notice"><AlertCircle size={16} /> Upload your original .tex resume in My profile to generate application documents.</div>}
      {(activeDoc === 'resume' || activeDoc === 'cover') && <div className="generated-panel">
        <div className="generated-heading"><div className="generated-heading-icon">{activeDoc === 'resume' ? <FileBadge size={17} /> : <FileText size={17} />}</div><div><h3>{activeDoc === 'resume' ? 'Tailored resume' : 'Cover letter'}</h3><p>{busy ? 'Gemma is preparing your document…' : 'Generated for this role'}</p></div><button className="icon-button" onClick={() => setActiveDoc('')} aria-label="Close generated document"><X size={16} /></button></div>
        {busy ? <div className="generation-loading"><Spinner /><div><b>Working on it</b><span>This can take a little while for a local model.</span></div></div> : null}
        {activeDoc === 'resume' && resumeResult && <div className="generated-content">
          <div className="download-actions"><Button size="sm" onClick={downloadResumePdf}><ArrowDownToLine size={15} /> Download PDF</Button><Button size="sm" variant="outline" onClick={downloadLatex}><FileCode2 size={15} /> Download .tex</Button></div>
          {pdfObjectUrl ? <iframe className="pdf-preview" title="Tailored resume PDF preview" src={pdfObjectUrl} /> : <div className="preview-fallback"><FileCheck2 size={24} /><p>Your PDF is ready. Download it to review your resume.</p></div>}
          <details className="source-details"><summary>View generated LaTeX source</summary><pre>{resumeResult.latex}</pre></details>
        </div>}
        {activeDoc === 'cover' && coverResult && <div className="generated-content"><div className="letter-preview">{coverResult.cover_letter}</div><Button size="sm" onClick={downloadCover}><ArrowDownToLine size={15} /> Download cover letter</Button></div>}
      </div>}
      <div className="detail-description-header"><h3>About this role</h3><button className="subtle-button" onClick={() => setShowDescription((old) => !old)}>{showDescription ? 'Collapse' : 'Expand'} <ChevronDown size={14} className={showDescription ? '' : 'rotate-chevron'} /></button></div>
      {showDescription && <div className="detail-description">{description ? <p>{description}</p> : <div className="description-missing"><FileText size={22} /><b>Description unavailable</b><span>The provider did not return a full description for this listing.</span></div>}</div>}
      <div className="detail-bottom"><span>Take your time. Apply with intent.</span><a href={job.job_url} target="_blank" rel="noreferrer">View on LinkedIn <ArrowUpRight size={13} /></a></div>
    </section>
  </div>;
}

function JobBoard({ user, setActiveView, setToast }) {
  const [jobs, setJobs] = useState([]);
  const [selectedJob, setSelectedJob] = useState(null);
  const [searchBusy, setSearchBusy] = useState(false);
  const [loadingCached, setLoadingCached] = useState(true);
  const [filterText, setFilterText] = useState('');
  const [limit, setLimit] = useState(25);
  const [onlyWithDescription, setOnlyWithDescription] = useState(false);
  const [sortMode, setSortMode] = useState('relevance');
  const [lastSearched, setLastSearched] = useState(null);
  const [showFilters, setShowFilters] = useState(false);
  const searchInputRef = useRef(null);

  const loadCached = useCallback(async () => {
    setLoadingCached(true);
    try {
      const result = await apiRequest(`/api/users/${user.id}/jobs?limit=100`);
      setJobs(result);
    } catch (error) { setToast({ type: 'error', message: error.message }); }
    finally { setLoadingCached(false); }
  }, [user.id, setToast]);

  useEffect(() => { loadCached(); }, [loadCached]);

  async function searchJobs(event) {
    event?.preventDefault();
    setSearchBusy(true);
    try {
      const result = await apiRequest(`/api/users/${user.id}/search`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh: true, limit }),
      });
      setJobs(result);
      setLastSearched(new Date());
      setToast({ type: 'success', message: `Search complete. ${result.length} ranked job${result.length === 1 ? '' : 's'} ready to review.` });
    } catch (error) { setToast({ type: 'error', message: error.message }); }
    finally { setSearchBusy(false); }
  }

  const visibleJobs = useMemo(() => {
    let result = jobs.filter((job) => {
      const q = filterText.trim().toLowerCase();
      const matches = !q || [job.position, job.company, job.location, job.description].some((s) => (s || '').toLowerCase().includes(q));
      return matches && (!onlyWithDescription || Boolean(job.description?.trim()));
    });
    if (sortMode === 'newest') result = [...result].sort((a, b) => String(b.posted_date || '').localeCompare(String(a.posted_date || '')));
    if (sortMode === 'company') result = [...result].sort((a, b) => String(a.company).localeCompare(String(b.company)));
    return result;
  }, [jobs, filterText, onlyWithDescription, sortMode]);

  const withSalary = jobs.filter((j) => j.salary_text && j.salary_text !== 'Not specified').length;
  const withDescription = jobs.filter((j) => Boolean(j.description?.trim())).length;
  const salaryFloor = user.salary_min ? moneyLabel(user.salary_min, user.salary_currency) : 'Flexible';

  return <>
    <div className="page-head jobs-page-head"><div><div className="eyebrow"><span className="eyebrow-spark"><Sparkles size={13} /></span> YOUR NEXT CHAPTER STARTS HERE</div><h1>Good things take <em>aalas.</em></h1><p>We’ll sort through the noise. You focus on finding the right fit.</p></div><div className="head-actions"><Button variant="outline" onClick={loadCached} disabled={searchBusy || loadingCached}><RefreshCw size={15} /> Refresh list</Button><Button onClick={searchJobs} loading={searchBusy}><Search size={16} /> Find new jobs</Button></div></div>
    <section className="search-hero">
      <div className="search-hero-copy"><div className="search-hero-icon"><Search size={20} /></div><div><h2>Make your next move count.</h2><p>Search based on your profile, then explore your best-fit openings.</p></div></div>
      <form className="job-search-bar" onSubmit={searchJobs}>
        <label className="search-input"><Search size={17} /><input ref={searchInputRef} value={filterText} onChange={(e) => setFilterText(e.target.value)} placeholder="Filter your saved results by role, company, skills…" /></label>
        <div className="search-divider" />
        <label className="limit-select"><span>Fetch</span><select value={limit} onChange={(e) => setLimit(Number(e.target.value))}><option value={10}>10 jobs</option><option value={25}>25 jobs</option><option value={50}>50 jobs</option><option value={75}>75 jobs</option></select></label>
        <Button type="submit" loading={searchBusy}><Search size={15} /> Search</Button>
      </form>
      <div className="search-context"><span><MapPin size={13} /> {user.locations}</span><i /><span><BriefcaseBusiness size={13} /> {user.target_roles}</span><i /><span><GraduationCap size={13} /> {user.experience_level}</span><button onClick={() => setActiveView('profile')}>Edit preferences <ArrowUpRight size={12} /></button></div>
    </section>
    <section className="stat-strip">
      <div className="stat-item"><span className="stat-icon stat-icon-violet"><BriefcaseBusiness size={17} /></span><div><strong>{jobs.length}</strong><small>Jobs in your list</small></div></div>
      <div className="stat-item"><span className="stat-icon stat-icon-green"><FileText size={17} /></span><div><strong>{withDescription}</strong><small>With descriptions</small></div></div>
      <div className="stat-item"><span className="stat-icon stat-icon-orange"><Sparkles size={17} /></span><div><strong>{withSalary}</strong><small>Salary disclosed</small></div></div>
      <div className="stat-update"><span className="status-pip" />{lastSearched ? `Last searched ${lastSearched.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}` : 'Ready when you are'}<span className="stat-update-line" /></div>
    </section>
    <section className="jobs-section">
      <div className="section-heading"><div><span className="section-overline">YOUR SHORTLIST</span><h2>Jobs worth a look <span className="count-pill">{visibleJobs.length}</span></h2><p>Sorted by hybrid relevance unless you choose another view.</p></div><div className="job-list-controls"><button className={`filter-toggle ${showFilters ? 'filter-active' : ''}`} onClick={() => setShowFilters((v) => !v)}><SlidersHorizontal size={15} /> Filters</button><label className="sort-select"><span>Sort:</span><select value={sortMode} onChange={(e) => setSortMode(e.target.value)}><option value="relevance">Relevance</option><option value="newest">Most recent</option><option value="company">Company A–Z</option></select><ChevronDown size={13} /></label></div></div>
      {showFilters && <div className="filter-row"><label className="filter-check"><input type="checkbox" checked={onlyWithDescription} onChange={(e) => setOnlyWithDescription(e.target.checked)} /> Only show jobs with descriptions</label><span className="filter-hint">Salary is optional and never treated as zero.</span><button className="subtle-button" onClick={() => { setOnlyWithDescription(false); setFilterText(''); setSortMode('relevance'); }}>Clear filters</button></div>}
      {loadingCached ? <div className="list-skeleton"><div /><div /><div /></div> : visibleJobs.length ? <div className="job-list">{visibleJobs.map((job, index) => <JobCard key={job.id} job={job} index={index} selected={selectedJob?.id === job.id} onSelect={setSelectedJob} />)}</div> : <div className="empty-state"><div className="empty-illustration"><div className="empty-sun" /><div className="empty-folder"><BriefcaseBusiness size={32} /></div><Sparkles className="empty-sparkle" size={20} /></div><h3>{jobs.length ? 'No jobs match those filters.' : 'A clean slate. A good place to start.'}</h3><p>{jobs.length ? 'Try a different keyword or clear the filters.' : 'Run your first search to fetch fresh openings matched to your profile.'}</p>{jobs.length ? <Button variant="outline" onClick={() => { setFilterText(''); setOnlyWithDescription(false); }}>Clear filters</Button> : <Button onClick={searchJobs} loading={searchBusy}><Sparkles size={16} /> Find my first jobs</Button>}</div>}
      <div className="list-footer"><span>Showing {visibleJobs.length} of {jobs.length} saved jobs</span><span className="footer-note"><Sparkles size={13} /> Ranked with keyword + semantic relevance</span></div>
    </section>
    <div className="bottom-tip"><div className="bottom-tip-icon"><Zap size={18} /></div><div><b>One thoughtful application beats ten rushed ones.</b><p>Open a role to tailor your resume and generate a role-specific cover letter.</p></div><button onClick={() => setActiveView('profile')}>Review your profile <ArrowRight size={15} /></button></div>
    {selectedJob && <JobDetails job={selectedJob} user={user} onClose={() => setSelectedJob(null)} onToast={setToast} resumeReady={Boolean(user.resume_uploaded)} />}
  </>;
}

function ProfilePage({ user, onUserUpdated, setToast }) {
  const [form, setForm] = useState({ name: user.name || '', target_roles: user.target_roles || '', locations: user.locations || '', job_type: user.job_type || 'full time', salary_min: user.salary_min ?? '', salary_currency: user.salary_currency || 'INR', experience_level: user.experience_level || 'entry level', additional_context: user.additional_context || '' });
  const [busy, setBusy] = useState(false);
  const [uploadBusy, setUploadBusy] = useState(false);
  const [file, setFile] = useState(null);
  const fileRef = useRef(null);
  useEffect(() => { setForm({ name: user.name || '', target_roles: user.target_roles || '', locations: user.locations || '', job_type: user.job_type || 'full time', salary_min: user.salary_min ?? '', salary_currency: user.salary_currency || 'INR', experience_level: user.experience_level || 'entry level', additional_context: user.additional_context || '' }); }, [user]);
  const update = (key, value) => setForm((f) => ({ ...f, [key]: value }));

  async function save(event) {
    event.preventDefault(); setBusy(true);
    try {
      const payload = { ...form, salary_min: form.salary_min === '' ? null : Number(form.salary_min) };
      const updated = await apiRequest(`/api/users/${user.id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      onUserUpdated(updated); setToast({ type: 'success', message: 'Your profile and search preferences were saved.' });
    } catch (error) { setToast({ type: 'error', message: error.message }); }
    finally { setBusy(false); }
  }

  async function upload(event) {
    event.preventDefault(); if (!file) { setToast({ type: 'error', message: 'Choose a .tex file first.' }); return; }
    setUploadBusy(true);
    try {
      const data = new FormData(); data.append('file', file);
      await apiRequest(`/api/users/${user.id}/resume`, { method: 'POST', body: data });
      const updated = await apiRequest(`/api/users/${user.id}`);
      onUserUpdated(updated); setFile(null); if (fileRef.current) fileRef.current.value = '';
      setToast({ type: 'success', message: 'Your LaTeX resume is uploaded and ready to tailor.' });
    } catch (error) { setToast({ type: 'error', message: error.message }); }
    finally { setUploadBusy(false); }
  }

  return <>
    <div className="page-head profile-page-head"><div><div className="eyebrow"><span className="eyebrow-spark"><UserRound size={13} /></span> YOUR CAREER PROFILE</div><h1>A little about <em>you.</em></h1><p>Keep your search preferences and resume current. Better input, better matches.</p></div><div className="profile-id-chip"><div className="avatar">{initials(user.name)}</div><div><b>{user.name}</b><small>Profile ID #{user.id}</small></div></div></div>
    <div className="profile-layout">
      <div className="profile-main-col">
        <section className="panel-card"><div className="panel-card-header"><div className="panel-icon icon-violet"><Settings2 size={18} /></div><div><h2>Search preferences</h2><p>These fields shape the jobs we fetch and rank.</p></div></div>
          <form className="profile-form" onSubmit={save}>
            <div className="form-grid"><label className="field"><span>Full name</span><input required value={form.name} onChange={(e) => update('name', e.target.value)} /></label><label className="field"><span>Email address</span><input disabled value={user.email} /><small className="field-footnote">Email editing isn't supported by the current API.</small></label></div>
            <label className="field"><span>Target job titles <small>Comma-separated roles</small></span><input required value={form.target_roles} onChange={(e) => update('target_roles', e.target.value)} /></label>
            <label className="field"><span>Preferred locations <small>Comma-separated locations</small></span><input required value={form.locations} onChange={(e) => update('locations', e.target.value)} /></label>
            <div className="form-grid"><label className="field"><span>Job type</span><select value={form.job_type} onChange={(e) => update('job_type', e.target.value)}><option value="full time">Full-time</option><option value="part time">Part-time</option><option value="contract">Contract</option><option value="temporary">Temporary</option><option value="internship">Internship</option></select></label><label className="field"><span>Experience level</span><select value={form.experience_level} onChange={(e) => update('experience_level', e.target.value)}><option value="internship">Internship</option><option value="entry level">Entry level</option><option value="associate">Associate</option><option value="senior">Senior</option><option value="director">Director</option><option value="executive">Executive</option></select></label></div>
            <div className="form-grid"><label className="field"><span>Minimum annual salary <small>Optional preference</small></span><input type="number" min="0" value={form.salary_min} onChange={(e) => update('salary_min', e.target.value)} placeholder="No minimum" /></label><label className="field"><span>Currency</span><select value={form.salary_currency} onChange={(e) => update('salary_currency', e.target.value)}><option value="INR">INR · Indian Rupee</option><option value="USD">USD · US Dollar</option><option value="EUR">EUR · Euro</option><option value="GBP">GBP · Pound</option></select></label></div>
            <label className="field"><span>Additional projects and experience <small>Context not already in your resume</small></span><textarea rows={5} value={form.additional_context} onChange={(e) => update('additional_context', e.target.value)} placeholder="Add relevant projects, work, achievements, or skills. AI must not invent details." /></label>
            <div className="form-bottom"><span><CheckCircle2 size={15} /> Changes apply to future searches and documents.</span><Button type="submit" loading={busy}><Check size={16} /> Save changes</Button></div>
          </form>
        </section>
      </div>
      <div className="profile-side-col">
        <section className="panel-card resume-card"><div className="panel-card-header"><div className="panel-icon icon-green"><FileCode2 size={18} /></div><div><h2>LaTeX resume</h2><p>Your original source is the starting point.</p></div></div>
          <div className={`resume-status ${user.resume_uploaded ? 'resume-status-ready' : 'resume-status-missing'}`}><div className="resume-status-icon">{user.resume_uploaded ? <CheckCircle2 size={17} /> : <AlertCircle size={17} />}</div><div><b>{user.resume_uploaded ? 'Resume uploaded' : 'Resume not uploaded'}</b><span>{user.resume_uploaded ? 'Ready for job-specific tailoring.' : 'Upload a .tex file to enable AI documents.'}</span></div></div>
          <form onSubmit={upload}>
            <button className={`resume-dropzone ${file ? 'resume-dropzone-selected' : ''}`} type="button" onClick={() => fileRef.current?.click()} onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); const f = e.dataTransfer.files?.[0]; if (f?.name.toLowerCase().endsWith('.tex') && f.size <= 1024 * 1024) setFile(f); else setToast({ type: 'error', message: 'Choose a .tex file of 1 MB or less.' }); }}>
              <input ref={fileRef} type="file" hidden accept=".tex,text/plain" onChange={(e) => { const f = e.target.files?.[0]; if (f && !f.name.toLowerCase().endsWith('.tex')) { setToast({ type: 'error', message: 'Resume must be a .tex file.' }); e.target.value = ''; return; } if (f && f.size > 1024 * 1024) { setToast({ type: 'error', message: 'Resume must be 1 MB or smaller.' }); e.target.value = ''; return; } setFile(f || null); }} />
              <div className="dropzone-icon"><Upload size={20} /></div><b>{file ? file.name : 'Choose a .tex file'}</b><span>{file ? `${(file.size / 1024).toFixed(0)} KB · ready to upload` : 'or drag and drop it here'}</span><small>UTF-8 · LaTeX source · Max 1 MB</small>
            </button>
            <Button type="submit" block loading={uploadBusy} disabled={!file}><Upload size={15} /> {user.resume_uploaded ? 'Replace resume' : 'Upload resume'}</Button>
          </form>
          <div className="resume-privacy"><FileCheck2 size={15} /><span>The .tex source is stored by your backend and sent to the AI service when you generate documents.</span></div>
        </section>
        <section className="profile-help-card"><div className="help-sparkle"><Sparkles size={19} /></div><h3>Useful context makes a difference.</h3><p>Add projects or experience that's missing from your resume. The AI can include it only when you provide the facts.</p><div className="help-check"><Check size={14} /> Preserve your LaTeX style</div><div className="help-check"><Check size={14} /> Don't invent achievements</div></section>
      </div>
    </div>
  </>;
}

function App() {
  const [user, setUser] = useState(null);
  const [activeView, setActiveView] = useState('jobs');
  const [toast, setToastState] = useState(null);
  const [booting, setBooting] = useState(true);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const setToast = useCallback((value) => setToastState(value), []);

  useEffect(() => {
    let live = true;
    async function restore() {
      const id = localStorage.getItem(ACTIVE_PROFILE_KEY);
      if (id) {
        try { const profile = await apiRequest(`/api/users/${id}`); if (live) setUser(profile); }
        catch { localStorage.removeItem(ACTIVE_PROFILE_KEY); }
      }
      if (live) setBooting(false);
    }
    restore();
    return () => { live = false; };
  }, []);

  const onCreated = useCallback((profile) => { setUser(profile); setActiveView('jobs'); }, []);
  const onUserUpdated = useCallback((profile) => setUser(profile), []);
  function resetProfile() {
    localStorage.removeItem(ACTIVE_PROFILE_KEY);
    setUser(null); setActiveView('jobs'); setToast({ type: 'success', message: 'This browser session has been cleared. Your backend profile was not deleted.' });
  }

  if (booting) return <div className="boot-screen"><div className="brand"><div className="brand-mark"><span>a</span></div><span>aalas<span className="brand-dot">.</span></span></div><Spinner /><span>Getting your workspace ready…</span></div>;
  if (!user) return <><Registration onCreated={onCreated} setToast={setToast} /><Toast toast={toast} onClose={() => setToastState(null)} /></>;

  return <div className="app-shell">
    <div className={`mobile-nav-scrim ${mobileNavOpen ? 'is-open' : ''}`} onClick={() => setMobileNavOpen(false)} />
    <div className={`sidebar-wrap ${mobileNavOpen ? 'mobile-nav-open' : ''}`}><Sidebar activeView={activeView} setActiveView={(view) => { setActiveView(view); setMobileNavOpen(false); }} user={user} onReset={resetProfile} /></div>
    <main className="main-shell">
      <Topbar user={user} activeView={activeView} setMobileNav={() => setMobileNavOpen(true)} />
      <div className="main-content">
        {activeView === 'jobs' ? <JobBoard user={user} setActiveView={setActiveView} setToast={setToast} /> : <ProfilePage user={user} onUserUpdated={onUserUpdated} setToast={setToast} />}
        <footer className="app-footer"><span>© 2026 Aalas. One good step at a time.</span><span><span className="footer-dot" /> Powered by your profile, pgvector & local AI</span></footer>
      </div>
    </main>
    <Toast toast={toast} onClose={() => setToastState(null)} />
  </div>;
}

export default App;
