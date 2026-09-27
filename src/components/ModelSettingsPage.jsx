import { useEffect, useMemo, useState } from "react";
import {
  ArrowsClockwise,
  BracketsCurly,
  Check,
  CheckCircle,
  DotsThree,
  LinkSimple,
  PencilSimple,
  Plus,
  Sparkle,
  Trash,
  X,
} from "@phosphor-icons/react";

const EMPTY_SETTINGS = {
  providerUrl: "",
  providerName: "External Video API",
  providerModel: "video-default",
  providerApiKey: "",
  apiKeySet: false,
  llmProviderUrl: "",
  llmProviderName: "OpenAI Compatible",
  llmModel: "gpt-4o-mini",
  llmVisionModel: "",
  llmApiKey: "",
  llmApiKeySet: false,
  voiceProvider: "mock",
  voiceModel: "voice-default",
  cosyvoiceUrl: "",
  chatterboxUrl: "",
  gptSovitsUrl: "",
};

const SERVICE_COPY = {
  llm: {
    label: "LLM / Agent",
    icon: Sparkle,
    description: "用于 Agent、剧本结构化输出和视觉 QC",
    typeLabel: "OpenAI-compatible",
    color: "blue",
  },
  media: {
    label: "图片 / 视频",
    icon: LinkSimple,
    description: "用于人物图、场景图和视频生成任务",
    typeLabel: "通用生成接口",
    color: "violet",
  },
};

const CATEGORY_LABELS = {
  text: "文本 / LLM",
  vision: "视觉理解",
  image: "图片生成",
  video: "视频生成",
  audio: "音频 / 语音",
  embedding: "向量 / 重排",
  workflow: "工作流",
  unknown: "未识别",
};

function providerDraft(settings, kind) {
  if (kind === "llm") {
    return {
      kind,
      name: settings.llmProviderName || "OpenAI Compatible",
      url: settings.llmProviderUrl || "",
      apiKey: "",
      apiKeySet: Boolean(settings.llmApiKeySet),
      defaultModel: settings.llmModel || "",
      visionModel: settings.llmVisionModel || "",
    };
  }
  return {
    kind,
    name: settings.providerName || "External Video API",
    url: settings.providerUrl || "",
    apiKey: "",
    apiKeySet: Boolean(settings.apiKeySet),
    defaultModel: settings.providerModel || "",
    visionModel: "",
  };
}

function providerPayload(draft) {
  if (draft.kind === "llm") {
    return {
      llmProviderName: draft.name,
      llmProviderUrl: draft.url,
      llmModel: draft.defaultModel,
      llmVisionModel: draft.visionModel,
      ...(draft.apiKey ? { llmApiKey: draft.apiKey } : {}),
    };
  }
  return {
    providerName: draft.name,
    providerUrl: draft.url,
    providerModel: draft.defaultModel,
    ...(draft.apiKey ? { providerApiKey: draft.apiKey } : {}),
  };
}

function generationEndpointPreview(draft) {
  if (!draft?.url || draft.kind !== "media") return "";
  const base = draft.url.replace(/\/+$/, "");
  const lowered = base.toLowerCase();
  if (lowered.endsWith("/images/generations") || lowered.endsWith("/image/generations") || lowered.endsWith("/videos/generations") || lowered.endsWith("/video/generations") || lowered.endsWith("/generate")) return base;
  if (lowered.endsWith("/v1") && /(gpt-image|image-2|dall-e|flux|stable-diffusion|sdxl|sd3|qwen-image|kolors|midjourney)/.test(String(draft.defaultModel || "").toLowerCase())) return `${base}/images/generations`;
  if (lowered.endsWith("/v1") && /(video|kling|seedance|wan2|vidu|runway|luma|hailuo)/.test(String(draft.defaultModel || "").toLowerCase())) return `${base}/videos/generations`;
  return base;
}

function modelList(catalog) {
  return (catalog?.models || []).map((item) => item.modelId).filter(Boolean);
}

function ModelPicker({ label, value, onChange, catalog, hint }) {
  const models = modelList(catalog);
  return <label className="model-route-field">
    <span>{label}</span>
    {models.length ? <select value={value || ""} onChange={(event) => onChange(event.target.value)}>
      <option value="">选择模型</option>
      {models.map((model) => <option value={model} key={model}>{model}</option>)}
    </select> : <input value={value || ""} onChange={(event) => onChange(event.target.value)} placeholder="先获取模型，或手动填写模型 ID" />}
    {hint && <small>{hint}</small>}
  </label>;
}

function CatalogPreview({ catalog, compact = false }) {
  if (!catalog) return <div className="catalog-empty"><BracketsCurly size={17} /><span>尚未获取模型目录</span></div>;
  return <div className={`catalog-preview ${compact ? "is-compact" : ""}`}>
    <div className="catalog-summary"><strong>{catalog.count} 个模型</strong><span title={catalog.endpoint}>{catalog.endpoint}</span></div>
    <div className="catalog-groups">
      {(catalog.groups || []).map((group) => <div className="catalog-group" key={group.type}>
        <div><b>{CATEGORY_LABELS[group.type] || group.label || group.type}</b><em>{group.count}</em></div>
        <p>{(group.models || []).slice(0, compact ? 3 : 6).map((model) => <span key={model.modelId} title={model.modelId}>{model.displayName || model.modelId}</span>)}</p>
      </div>)}
    </div>
  </div>;
}

function ServiceCard({ kind, settings, catalog, active, onEdit, onDelete }) {
  const copy = SERVICE_COPY[kind];
  const Icon = copy.icon;
  const configured = Boolean(kind === "llm" ? settings.llmProviderUrl : settings.providerUrl);
  const name = kind === "llm" ? settings.llmProviderName : settings.providerName;
  const url = kind === "llm" ? settings.llmProviderUrl : settings.providerUrl;
  const model = kind === "llm" ? settings.llmModel : settings.providerModel;
  const visionModel = kind === "llm" ? settings.llmVisionModel : "";
  return <article className={`model-service-card ${active ? "is-active" : ""} ${!configured ? "is-empty" : ""}`}>
    <div className={`service-icon ${copy.color}`}><Icon size={24} weight="duotone" /></div>
    <div className="service-card-main">
      <div className="service-card-title"><h3>{name || copy.label}</h3><span>{copy.typeLabel}</span>{active && <em><CheckCircle size={14} weight="fill" />当前使用</em>}</div>
      <p>{configured ? url : `还没有配置${copy.label}服务`}</p>
      {configured ? <>
        <div className="service-card-meta"><span>{catalog ? `${catalog.count} 个配置模型` : "模型目录未读取"}</span><span>默认：{model || "未选择"}</span>{visionModel && <span>视觉：{visionModel}</span>}</div>
        <div className="service-card-status"><CheckCircle size={15} weight="fill" />{copy.description}</div>
      </> : <div className="service-card-status muted">点击“添加模型服务”开始配置</div>}
    </div>
    <div className="service-card-actions">
      <button type="button" className="card-menu" aria-label={`${name || copy.label} 更多操作`}><DotsThree size={22} /></button>
      <button type="button" onClick={onEdit}><PencilSimple size={15} />编辑</button>
      {configured && <button type="button" className="danger" onClick={onDelete}><Trash size={15} />删除</button>}
    </div>
  </article>;
}

function ModelServiceModal({ draft, catalog, busy, notice, onChange, onTest, onDiscover, onSave, onClose }) {
  if (!draft) return null;
  const copy = SERVICE_COPY[draft.kind];
  return <div className="model-modal-backdrop" onMouseDown={onClose}>
    <section className="model-service-modal" onMouseDown={(event) => event.stopPropagation()}>
      <header className="model-modal-header"><div><span className="settings-kicker">NEW MODEL SERVICE</span><h2>{draft.url ? "编辑模型服务" : "添加模型服务"}</h2><p>填写接口信息，测试连接后获取模型目录；密钥只保存在本机安全存储。</p></div><button type="button" onClick={onClose} aria-label="关闭"><X size={22} /></button></header>
      <div className="model-modal-body">
        <label className="modal-field wide"><span>服务名称</span><input value={draft.name} onChange={(event) => onChange({ name: event.target.value })} placeholder="例如：DeepSeek 官方、公司中转 API" /></label>
        <div className="service-type-options"><button type="button" className={draft.kind === "llm" ? "is-selected" : ""} onClick={() => onChange({ kind: "llm", ...providerDraft({ llmProviderName: draft.name, llmProviderUrl: draft.url, llmModel: draft.defaultModel, llmVisionModel: draft.visionModel, llmApiKeySet: draft.apiKeySet }, "llm") })}><Sparkle size={18} /><strong>LLM / Agent</strong><small>文本、视觉与结构化输出</small></button><button type="button" className={draft.kind === "media" ? "is-selected" : ""} onClick={() => onChange({ kind: "media", ...providerDraft({ providerName: draft.name, providerUrl: draft.url, providerModel: draft.defaultModel, apiKeySet: draft.apiKeySet }, "media") })}><LinkSimple size={18} /><strong>图片 / 视频</strong><small>人物图、场景图与视频生成</small></button></div>
        <div className="modal-field-grid"><label className="modal-field"><span>{draft.kind === "media" ? "Base URL / 生成地址" : "Base URL"}</span><input value={draft.url} onChange={(event) => onChange({ url: event.target.value })} placeholder={draft.kind === "llm" ? "https://api.openai.com/v1" : "https://api.example.com/v1"} />{draft.kind === "media" && draft.url && <small className="endpoint-preview">实际提交：{generationEndpointPreview(draft)}</small>}</label><label className="modal-field"><span>API Key <i>仅保存在本机</i></span><input type="password" value={draft.apiKey} onChange={(event) => onChange({ apiKey: event.target.value })} placeholder={draft.apiKeySet ? "已保存密钥，留空保持不变" : "输入 API Key"} autoComplete="off" /></label></div>
        <div className="modal-actions"><button type="button" onClick={onTest} disabled={busy || !draft.url}><Check size={17} />测试连接</button><button type="button" onClick={onDiscover} disabled={busy || !draft.url}><ArrowsClockwise size={17} />{busy === "discover" ? "获取中…" : "获取模型"}</button><span>{busy === "test" ? "测试中…" : notice || "新配置未保存"}</span></div>
        <section className="model-routing-section"><div className="routing-heading"><div><span className="settings-kicker">MODEL ROUTING</span><h3>核心模型</h3><p>只需配置默认模型；视觉模型用于 QC 和图像理解。</p></div><strong>{catalog ? `已获取 ${catalog.count} 个模型` : "尚未获取目录"}</strong></div><div className="model-route-grid"><ModelPicker label="默认模型" value={draft.defaultModel} onChange={(value) => onChange({ defaultModel: value })} catalog={catalog} hint="Agent、文本或通用生成任务" />{draft.kind === "llm" && <ModelPicker label="视觉模型" value={draft.visionModel} onChange={(value) => onChange({ visionModel: value })} catalog={catalog} hint="支持图像输入的 VL / vision 模型" />}</div><CatalogPreview catalog={catalog} /></section>
        {draft.kind === "media" && <div className="modal-tip"><Sparkle size={17} /><span>通用图片/视频接口需要填写实际 POST 生成地址，不是网站首页。若返回 task_id，请在保存后补充异步状态地址。</span></div>}
      </div>
      <footer className="model-modal-footer"><button type="button" onClick={onClose}>取消</button><button type="button" className="primary-action" onClick={onSave} disabled={busy || !draft.url}>{busy === "save" ? "保存中…" : "保存并设为当前"}<Plus size={17} /></button></footer>
    </section>
  </div>;
}

export function ModelSettingsPage({ project, onUpdateProject, backendStatus, providerInfo, actions }) {
  const [settings, setSettings] = useState(EMPTY_SETTINGS);
  const [catalogs, setCatalogs] = useState({ llm: null, media: null });
  const [draft, setDraft] = useState(null);
  const [notice, setNotice] = useState("");
  const [modalNotice, setModalNotice] = useState("");
  const [busy, setBusy] = useState("");
  const [loading, setLoading] = useState(true);

  const loadCatalog = async (kind, nextSettings = settings) => {
    const source = providerDraft(nextSettings, kind);
    if (!source.url) return null;
    try {
      const result = await actions.discoverModels({ kind: kind === "llm" ? "llm" : "video", url: source.url, apiKey: source.apiKey, providerName: source.name });
      setCatalogs((current) => ({ ...current, [kind]: result }));
      return result;
    } catch {
      return null;
    }
  };

  useEffect(() => {
    if (backendStatus !== "online") {
      setLoading(false);
      return;
    }
    actions.getProviderSettings().then(async (next) => {
      const merged = { ...EMPTY_SETTINGS, ...next };
      setSettings(merged);
      setLoading(false);
      await Promise.all([loadCatalog("llm", merged), loadCatalog("media", merged)]);
    }).catch(() => {
      setLoading(false);
      setNotice("模型服务配置读取失败，请确认 FastAPI 正在运行。");
    });
  }, [backendStatus]);

  const configured = useMemo(() => [settings.llmProviderUrl, settings.providerUrl].filter(Boolean).length, [settings]);
  const modelCount = (catalogs.llm?.count || 0) + (catalogs.media?.count || 0);
  const currentLabel = settings.llmProviderUrl && settings.providerUrl
    ? `LLM：${settings.llmProviderName} · 生成：${settings.providerName}`
    : settings.llmProviderUrl ? `LLM：${settings.llmProviderName}` : settings.providerUrl ? `生成：${settings.providerName}` : "未配置";

  const openService = (kind) => {
    setDraft(providerDraft(settings, kind));
    setModalNotice("");
  };

  const updateDraft = (patch) => setDraft((current) => ({ ...current, ...patch }));

  const discoverDraft = async () => {
    if (!draft?.url) return;
    setBusy("discover");
    setModalNotice("");
    try {
      const result = await actions.discoverModels({ kind: draft.kind === "llm" ? "llm" : "video", url: draft.url, apiKey: draft.apiKey, providerName: draft.name });
      setCatalogs((current) => ({ ...current, [draft.kind]: result }));
      const recommended = result.recommended || {};
      setDraft((current) => ({ ...current, defaultModel: current.defaultModel || recommended.text || recommended.image || recommended.video || "", visionModel: current.visionModel || recommended.vision || "" }));
      setModalNotice(`已发现 ${result.count} 个模型，并自动完成分类。`);
    } catch (error) {
      setModalNotice(error?.message || "模型目录读取失败，请确认接口支持 /models");
    } finally {
      setBusy("");
    }
  };

  const testDraft = async () => {
    if (!draft?.url) return;
    setBusy("test");
    setModalNotice("");
    try {
      const result = await actions.testProviderSettings({ ...providerPayload(draft), kind: draft.kind === "llm" ? "llm" : "video" });
      setModalNotice(result.message || (result.ok ? "接口连接成功" : "接口连接失败"));
      if (result.ok) await discoverDraft();
    } catch (error) {
      setModalNotice(error?.message || "接口测试失败");
    } finally {
      setBusy("");
    }
  };

  const saveDraft = async () => {
    if (!draft?.url) return;
    setBusy("save");
    try {
      const next = await actions.saveProviderSettings(providerPayload(draft));
      const merged = { ...EMPTY_SETTINGS, ...next };
      setSettings(merged);
      setDraft(null);
      setNotice(`${draft.name || SERVICE_COPY[draft.kind].label} 已保存，新的任务会使用 ${draft.defaultModel || "默认模型"}。`);
      await loadCatalog(draft.kind, merged);
      window.dispatchEvent(new Event("short-drama-settings-saved"));
    } catch (error) {
      setModalNotice(error?.message || "保存失败");
    } finally {
      setBusy("");
    }
  };

  const deleteService = async (kind) => {
    const isLLM = kind === "llm";
    const label = isLLM ? settings.llmProviderName : settings.providerName;
    setBusy(`delete-${kind}`);
    try {
      const next = await actions.saveProviderSettings(isLLM ? { llmProviderUrl: "", llmProviderName: "OpenAI Compatible", llmModel: "gpt-4o-mini", llmVisionModel: "", llmApiKey: "__CLEAR__" } : { providerUrl: "", providerName: "External Video API", providerModel: "video-default", providerApiKey: "__CLEAR__" });
      setSettings({ ...EMPTY_SETTINGS, ...next });
      setCatalogs((current) => ({ ...current, [kind]: null }));
      setNotice(`${label} 已删除`);
    } catch (error) {
      setNotice(error?.message || "删除失败");
    } finally {
      setBusy("");
    }
  };

  return <div className="module-page model-settings-page">
    <div className="model-settings-header"><div><span className="settings-kicker">MODEL &amp; API</span><h1>模型与 API</h1><p>集中管理接口、密钥和模型目录。</p></div><button className="primary-action add-service-button" type="button" onClick={() => openService("llm")}><Plus size={19} />添加模型服务</button></div>
    <div className="settings-summary"><span><i className="summary-dot" />{configured} 个服务</span><span><i className="summary-dot" />{modelCount || configured} 个配置模型</span><span><i className="summary-dot" />当前使用：{currentLabel}</span></div>
    {notice && <div className="settings-inline-notice"><CheckCircle size={16} weight="fill" />{notice}</div>}
    {backendStatus !== "online" && <div className="settings-inline-notice warning"><span>FastAPI 未连接，模型服务不能保存或测试。</span></div>}
    <section className="model-services-list">
      {loading ? <div className="model-settings-loading">正在读取模型服务…</div> : <>
        <ServiceCard kind="llm" settings={settings} catalog={catalogs.llm} active={Boolean(settings.llmProviderUrl)} onEdit={() => openService("llm")} onDelete={() => deleteService("llm")} />
        <ServiceCard kind="media" settings={settings} catalog={catalogs.media} active={Boolean(settings.providerUrl)} onEdit={() => openService("media")} onDelete={() => deleteService("media")} />
      </>}
    </section>
    <section className="module-section model-project-settings"><div><span className="settings-kicker">PROJECT</span><h2>项目基础信息</h2><p>与模型服务分开管理，避免配置页信息过载。</p></div><div className="project-settings-grid"><label>项目名称<input value={project.title} onChange={(event) => onUpdateProject({ title: event.target.value })} /></label><label>项目状态<select value={project.status} onChange={(event) => onUpdateProject({ status: event.target.value })}>{["策划中", "制作中", "审核中", "已完成"].map((item) => <option key={item}>{item}</option>)}</select></label><label>预算（元）<input type="number" min="0" value={project.budget} onChange={(event) => onUpdateProject({ budget: Number(event.target.value) })} /></label><label>计划完成日期<input type="date" value={project.dueDate} onChange={(event) => onUpdateProject({ dueDate: event.target.value })} /></label></div></section>
    <section className="model-settings-runtime"><div><span className="settings-kicker">RUNTIME</span><h3>当前运行状态</h3><p>{backendStatus === "online" ? (providerInfo?.mode === "remote" ? "已配置外部 Provider，新任务会写入持久队列并由后台执行。" : "当前使用本地演示 Provider；配置服务后会自动切换。") : "FastAPI 未连接，生成任务无法同步到服务端。"}</p></div><strong>{providerInfo?.mode === "remote" ? "Remote" : "Local Demo"}</strong></section>
    {draft && <ModelServiceModal draft={draft} catalog={catalogs[draft.kind]} busy={busy} notice={modalNotice} onChange={updateDraft} onTest={testDraft} onDiscover={discoverDraft} onSave={saveDraft} onClose={() => setDraft(null)} />}
  </div>;
}
