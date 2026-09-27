import { useEffect, useMemo, useState } from "react";
import {
  ArrowRight,
  Check,
  CheckCircle,
  Clock,
  DownloadSimple,
  FilmStrip,
  Images,
  MagnifyingGlass,
  Plus,
  Play,
  Robot,
  Sparkle,
  SpeakerHigh,
  Stop,
  Trash,
  Warning,
  X,
} from "@phosphor-icons/react";
import { ModelSettingsPage } from "./ModelSettingsPage.jsx";

function PageHeader({ eyebrow, title, description, action }) {
  return <div className="module-header"><div><span>{eyebrow}</span><h1>{title}</h1><p>{description}</p></div>{action}</div>;
}

const agentPlan = [
  ["context", "读取故事上下文", "故事圣经、角色规则与当前剧集状态"],
  ["matrix", "推进剧集矩阵", "锁定开场钩子、核心事件和结尾问题"],
  ["scene", "准备可拍场景", "复用已有场景，没有就自动创建"],
  ["script", "生成场景剧本", "把场景目的写成动作与对白节拍"],
  ["breakdown", "拆解生产镜头", "生成景别、时长和下一步生产任务"],
];

function AgentPage({ project, stats, actions }) {
  const [episodeId, setEpisodeId] = useState(project.currentEpisodeId);
  const [goal, setGoal] = useState(() => `把 ${project.currentEpisodeId} 做成可拍分镜，保持人物关系和故事规则连续`);
  const [running, setRunning] = useState(false);
  const [stepState, setStepState] = useState(() => agentPlan.map(([id]) => ({ id, status: "pending" })));
  const [logs, setLogs] = useState(["Agent 已就绪，等待你的制作目标。"]);
  const [result, setResult] = useState("");
  const [runId, setRunId] = useState(null);

  useEffect(() => {
    if (project.currentEpisodeId && project.currentEpisodeId !== episodeId && !running) {
      setEpisodeId(project.currentEpisodeId);
    }
  }, [project.currentEpisodeId, running]);

  const episode = project.episodes.find((item) => item.id === episodeId) || project.episodes[0];
  const currentShots = project.shots.filter((shot) => shot.episodeId === episodeId);
  const syncRun = (run) => {
    setRunId(run?.id || null);
    setStepState(agentPlan.map(([id]) => ({ id, status: run?.steps?.find((step) => step.key === id)?.status === "success" ? "done" : run?.steps?.find((step) => step.key === id)?.status || "pending" })));
    const nextLogs = (run?.steps || []).filter((step) => step.status === "success").map((step) => `${step.title}：已完成${step.output?.provider === "local-fallback" ? "（本地降级模式）" : ""}`);
    setLogs(nextLogs.length ? nextLogs : ["Agent 已创建持久化执行记录，等待后台领取任务。"]);
    if (run?.status === "success") setResult(`已完成 ${run.episodeId}：Agent 已准备场景和分镜，下一步可进入分镜工作台审核。`);
    if (run?.status === "failed") setResult(`本轮执行已暂停：${run.error || "请处理错误后恢复执行"}`);
  };

  const pollAgent = async (id) => {
    try {
      const run = await actions.getAgentRun(id);
      syncRun(run);
      if (["queued", "running"].includes(run.status)) {
        window.setTimeout(() => pollAgent(id), 900);
      } else {
        setRunning(false);
      }
    } catch (error) {
      setRunning(false);
      setResult(error?.message || "Agent 状态读取失败");
    }
  };

  useEffect(() => {
    if (actions.backendStatus !== "online") return undefined;
    let active = true;
    actions.listAgentRuns(episodeId).then((runs) => {
      if (!active || !runs[0]) return;
      syncRun(runs[0]);
      if (["queued", "running"].includes(runs[0].status)) {
        setRunning(true);
        pollAgent(runs[0].id);
      }
    }).catch(() => {});
    return () => { active = false; };
  }, [actions.backendStatus, episodeId]);

  const runAgent = async () => {
    if (running || actions.backendStatus !== "online") return;
    setRunning(true);
    setResult("");
    setStepState(agentPlan.map(([id]) => ({ id, status: "pending" })));
    setLogs([`收到目标：${goal.trim() || `推进 ${episodeId} 的剧本生产`}`]);
    try {
      const run = await actions.startAgentRun({ projectId: project.id, episodeId, goal });
      syncRun(run);
      pollAgent(run.id);
    } catch (error) {
      setRunning(false);
      setResult(error?.message || "Agent 启动失败");
    }
  };

  const stopAgent = async () => {
    if (!runId) return;
    try {
      const run = await actions.cancelAgentRun(runId);
      syncRun(run);
    } catch (error) {
      setResult(error?.message || "Agent 停止失败");
    } finally {
      setRunning(false);
    }
  };

  const resumeAgent = async () => {
    if (!runId || running) return;
    setRunning(true);
    try {
      const run = await actions.resumeAgentRun(runId);
      syncRun(run);
      pollAgent(run.id);
    } catch (error) {
      setRunning(false);
      setResult(error?.message || "Agent 断点恢复失败");
    }
  };

  return <div className="module-page agent-page">
    <PageHeader eyebrow="Agent Control Center" title="剧本 Agent" description="用一句话下达制作目标，Agent 会读取上下文、调用 API，并把结果推进到可审核的镜头。" action={<span className={`agent-runtime ${actions.backendStatus}`}>{actions.backendStatus === "online" ? "FastAPI 已连接" : "等待 API"}</span>} />
    <div className="agent-layout">
      <section className="module-section agent-command-card">
        <div className="section-heading"><div><h2>告诉 Agent 你要什么</h2><p>目标越接近结果，Agent 越少打断你。</p></div><Robot size={24} weight="duotone" /></div>
        <label className="agent-episode-field">工作剧集<select value={episodeId} onChange={(event) => { setEpisodeId(event.target.value); actions.updateProject({ currentEpisodeId: event.target.value }); }}><option value="">选择剧集</option>{project.episodes.map((item) => <option key={item.id} value={item.id}>{item.id}　{item.title}</option>)}</select></label>
        <label className="agent-goal-field"><span>制作目标</span><textarea value={goal} onChange={(event) => setGoal(event.target.value)} placeholder="例如：把 EP08 写成一场有反转的天台对峙，并拆成可生成镜头" /></label>
        <div className="agent-suggestions"><span>快速开始</span><button type="button" onClick={() => setGoal(`完成 ${episodeId} 的剧本到分镜流程`)}>完成本集到分镜</button><button type="button" onClick={() => setGoal(`为 ${episodeId} 补齐冲突升级和结尾钩子`)}>补齐本集节奏</button><button type="button" onClick={() => setGoal(`检查 ${episodeId} 的角色规则并修正镜头连续性`)}>检查连续性</button></div>
        <div className="agent-command-footer"><span>{actions.backendStatus === "online" ? "Agent 会持久化每一步，服务重启后可以继续。" : "FastAPI 未连接，暂时不能执行 Agent 任务。"}</span><div className="agent-command-actions">{!running && runId && stepState.some((step) => step.status === "failed") && <button type="button" onClick={resumeAgent}>从断点继续</button>}<button className="primary-action" type="button" onClick={running ? stopAgent : runAgent} disabled={actions.backendStatus !== "online"}>{running ? <><Stop size={16} />停止 Agent</> : <><Play size={16} weight="fill" />开始执行</>}</button></div></div>
      </section>
      <section className="module-section agent-plan-card">
        <div className="section-heading"><div><h2>Agent 执行计划</h2><p>每一步都有结果，随时可以回到工作台人工接管。</p></div><span className="agent-plan-count">{stepState.filter((step) => step.status === "done").length} / {stepState.length}</span></div>
        <div className="agent-plan-list">{agentPlan.map(([id, title, detail], index) => { const state = stepState.find((step) => step.id === id)?.status || "pending"; return <div className={`agent-plan-step ${state}`} key={id}><i>{state === "done" ? <Check size={14} weight="bold" /> : state === "running" ? <Sparkle size={14} /> : state === "failed" ? "!" : index + 1}</i><div><strong>{title}</strong><small>{detail}</small></div><em>{state === "done" ? "完成" : state === "running" ? "执行中" : state === "failed" ? "已暂停" : "等待"}</em></div>; })}</div>
      </section>
    </div>
    <div className="agent-lower-grid">
      <section className="module-section agent-log-card"><div className="section-heading"><div><h2>执行日志</h2><p>Agent 的每个动作都会留下可追踪记录。</p></div><span className={`agent-live-dot ${running ? "is-live" : ""}`}>{running ? "LIVE" : "IDLE"}</span></div><div className="agent-log-list">{logs.map((log, index) => <div key={`${log}-${index}`}><span>{String(index + 1).padStart(2, "0")}</span><p>{log}</p></div>)}</div>{result && <div className="agent-result"><Check size={16} weight="bold" /><span>{result}</span></div>}</section>
      <section className="module-section agent-memory-card"><div className="section-heading"><div><h2>Agent 记忆</h2><p>本轮执行会继承这些项目上下文。</p></div></div><div className="agent-memory-summary"><div><span>当前剧集</span><strong>{episode?.id} · {episode?.title}</strong><small>{currentShots.length} 个已有镜头</small></div><div><span>故事规则</span><strong>{project.storyBible.rules.length} 条不可违反规则</strong><small>自动注入生成请求</small></div><div><span>工作模式</span><strong>先计划，再执行</strong><small>关键节点保留人工接管</small></div></div><div className="agent-rule-preview">{project.storyBible.rules.slice(0, 3).map((rule, index) => <p key={`${rule}-${index}`}><i>{index + 1}</i>{rule}</p>)}</div></section>
    </div>
  </div>;
}

function OverviewPage({ project, stats, onNavigate }) {
  const progress = Math.round(project.production.generatedShots / project.production.totalShots * 100);
  const currentEpisode = project.episodes.find((episode) => episode.id === project.currentEpisodeId);
  return <div className="module-page overview-page">
    <PageHeader eyebrow="项目概览" title={`《${project.title}》`} description="从当前生产状态继续，处理最重要的下一步。" action={<button className="primary-action" type="button" onClick={() => onNavigate("分镜")}>继续制作 {currentEpisode?.id}<ArrowRight size={18} /></button>} />
    <section className="overview-hero">
      <div className="overview-progress"><div className="stage-row"><strong>当前阶段：分镜与视频生成</strong><span>{progress}%</span></div><div className="big-progress"><span style={{ width: `${progress}%` }} /></div><div className="stage-steps">{["剧本", "资产", "分镜", "生成", "质检", "导出"].map((item, index) => <span className={index <= 3 ? "done" : ""} key={item}><i>{index < 3 ? <Check size={12} weight="bold" /> : index + 1}</i>{item}</span>)}</div></div>
      <div className="overview-metrics"><div><span>当前剧集</span><strong>{currentEpisode?.id} / {project.targetEpisodes}</strong><small>{currentEpisode?.title}</small></div><div><span>镜头进度</span><strong>{project.production.generatedShots} / {project.production.totalShots}</strong><small>已生成 / 总镜头</small></div><div><span>QC 通过率</span><strong>{project.production.qcScore}%</strong><small>{stats.review} 个镜头待审核</small></div><div><span>预算</span><strong>¥{project.spent.toFixed(2)}</strong><small>剩余 ¥{(project.budget - project.spent).toFixed(2)}</small></div></div>
    </section>
    <div className="module-grid two-columns">
      <section className="module-section"><div className="section-heading"><div><h2>下一步</h2><p>系统根据任务状态生成的建议。</p></div></div><div className="next-actions"><button type="button" onClick={() => onNavigate("生成")}><span className="action-icon blue"><Sparkle size={19} /></span><span><strong>处理 {stats.failed} 个失败任务</strong><small>切换模型或编辑提示词后重试</small></span><ArrowRight size={18} /></button><button type="button" onClick={() => onNavigate("质检")}><span className="action-icon green"><CheckCircle size={19} /></span><span><strong>审核 {stats.review} 个镜头</strong><small>检查连续性与角色一致性</small></span><ArrowRight size={18} /></button><button type="button" onClick={() => onNavigate("分镜")}><span className="action-icon amber"><FilmStrip size={19} /></span><span><strong>完成 {stats.pending} 个待生成镜头</strong><small>补齐 EP08 场景 3</small></span><ArrowRight size={18} /></button></div></section>
      <section className="module-section"><div className="section-heading"><div><h2>最近剧集</h2><p>当前项目的生产节奏。</p></div><button type="button" onClick={() => onNavigate("剧集")}>查看全部</button></div><div className="episode-rows">{project.episodes.slice(5, 10).map((episode) => <button type="button" key={episode.id} onClick={() => onNavigate("剧集")}><span><strong>{episode.id}</strong><small>{episode.title}</small></span><em className={`episode-status ${episode.status}`}>{episode.status}</em><span>{episode.shots || "--"} 镜头</span></button>)}</div></section>
    </div>
  </div>;
}

function StoryPage({ project, onUpdateStory, onAddRule, onRemoveRule }) {
  const [newRule, setNewRule] = useState("");
  const fields = [
    ["logline", "一句话梗概"], ["coreConflict", "核心冲突"], ["mainLine", "故事主线"],
    ["theme", "主题"], ["ending", "最终结局"], ["world", "世界观"], ["style", "视觉风格"],
  ];
  return <div className="module-page"><PageHeader eyebrow="Story Bible" title="故事圣经" description="所有后续剧本、资产和镜头生成都以这里的规则为准。" />
    <div className="story-layout"><section className="module-section story-form">{fields.map(([field, label]) => <label key={field}><span>{label}</span><textarea value={project.storyBible[field]} onChange={(event) => onUpdateStory(field, event.target.value)} /></label>)}</section><section className="module-section rules-panel"><div className="section-heading"><div><h2>故事规则</h2><p>AI 生成剧情时不可违反。</p></div></div><div className="rule-list">{project.storyBible.rules.map((rule, index) => <div key={`${rule}-${index}`}><span>{index + 1}</span><p>{rule}</p><button type="button" aria-label="删除规则" onClick={() => onRemoveRule(index)}><Trash size={15} /></button></div>)}</div><form onSubmit={(event) => { event.preventDefault(); onAddRule(newRule); setNewRule(""); }}><input value={newRule} onChange={(event) => setNewRule(event.target.value)} placeholder="添加一条不能被违反的规则" /><button type="submit"><Plus size={16} />添加</button></form></section></div>
  </div>;
}

const scriptSteps = [
  ["bible", "故事圣经", "统一规则"],
  ["matrix", "剧集矩阵", "拆出本集节奏"],
  ["scene", "场景剧本", "写成可拍场景"],
  ["breakdown", "分镜拆解", "进入生产"],
];

function episodeMatrix(project, episodeId) {
  const episode = project.episodes.find((item) => item.id === episodeId) || {};
  return {
    hook: episode.hook || episode.openingHook || "",
    coreEvent: episode.coreEvent || "",
    payoff: episode.payoff || "",
    twist: episode.twist || "",
    endingHook: episode.endingHook || "",
  };
}

function ScriptPage({ project, actions }) {
  const [step, setStep] = useState("bible");
  const [episodeId, setEpisodeId] = useState(project.currentEpisodeId);
  const [sceneId, setSceneId] = useState(project.currentScene?.id || null);
  const [scenes, setScenes] = useState([]);
  const [matrix, setMatrix] = useState(() => episodeMatrix(project, project.currentEpisodeId));
  const [sceneDraft, setSceneDraft] = useState({ title: "", purpose: "", summary: "", timeOfDay: "" });
  const [scriptDraft, setScriptDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [sourceDraft, setSourceDraft] = useState("");
  const [storyQuality, setStoryQuality] = useState(null);

  const episode = project.episodes.find((item) => item.id === episodeId) || project.episodes[0];
  const scene = scenes.find((item) => item.id === sceneId) || null;
  const sceneShots = project.shots.filter((shot) => shot.sceneId === sceneId);
  const currentStep = scriptSteps.findIndex(([id]) => id === step);

  useEffect(() => {
    setMatrix(episodeMatrix(project, episodeId));
  }, [episodeId, project.episodes]);

  useEffect(() => {
    if (project.currentEpisodeId && project.currentEpisodeId !== episodeId) {
      setEpisodeId(project.currentEpisodeId);
    }
  }, [project.currentEpisodeId]);

  useEffect(() => {
    let active = true;
    setBusy(true);
    actions.loadScenes(episodeId).then((items) => {
      if (!active) return;
      setScenes(items);
      setSceneId((current) => items.some((item) => item.id === current) ? current : items[0]?.id || null);
    }).catch(() => {
      if (active) setNotice("场景读取失败，请检查 API 连接");
    }).finally(() => active && setBusy(false));
    return () => { active = false; };
  }, [episodeId]);

  useEffect(() => {
    if (episodeId && project.currentEpisodeId !== episodeId) actions.updateProject({ currentEpisodeId: episodeId });
  }, [episodeId]);

  useEffect(() => {
    if (!scene) {
      setSceneDraft({ title: "", purpose: "", summary: "", timeOfDay: "" });
      setScriptDraft("");
      return;
    }
    setSceneDraft({ title: scene.title || "", purpose: scene.purpose || "", summary: scene.summary || "", timeOfDay: scene.timeOfDay || "" });
    setScriptDraft((scene.script?.beats || []).map((beat) => beat.text || "").join("\n"));
  }, [sceneId, scenes]);

  const run = async (operation, successMessage, after) => {
    setBusy(true);
    setNotice("");
    try {
      const result = await operation();
      after?.(result);
      setNotice(successMessage);
    } catch (error) {
      setNotice(error?.message || "操作失败，请稍后重试");
    } finally {
      setBusy(false);
    }
  };

  const saveMatrix = () => run(() => actions.saveEpisode(episodeId, matrix), "本集矩阵已保存");
  const generateMatrix = () => run(() => actions.generateMatrix(episodeId, matrix), "已生成一版剧集矩阵", (result) => setMatrix(episodeMatrix({ episodes: [result] }, episodeId)));
  const createScene = () => run(() => actions.createScene(episodeId, { title: `场景 ${scenes.length + 1}`, summary: matrix.coreEvent, purpose: matrix.coreEvent, timeOfDay: "夜晚" }), "已创建场景", (result) => { setScenes((current) => [...current, result]); setSceneId(result.id); setStep("scene"); });
  const saveScene = () => run(() => actions.saveScene(sceneId, sceneDraft), "场景信息已保存", (result) => setScenes((current) => current.map((item) => item.id === sceneId ? result : item)));
  const generateScript = () => {
    const beats = scriptDraft.split("\n").map((text) => text.trim()).filter(Boolean).map((text, index) => ({ type: index === 1 ? "dialogue" : "action", text }));
    return run(() => actions.generateSceneScript(sceneId, { ...sceneDraft, script: beats.length ? { beats } : undefined }), "已生成场景剧本", (result) => { setScenes((current) => current.map((item) => item.id === sceneId ? result : item)); setScriptDraft((result.script?.beats || []).map((beat) => beat.text || "").join("\n")); });
  };
  const generateBreakdown = () => run(() => actions.generateBreakdown(sceneId), "已生成分镜拆解");
  const developStory = () => run(
    () => actions.developStory({ sourceText: sourceDraft }),
    "全剧 Story Engine 已更新",
    (result) => setStoryQuality(result.quality || null),
  );
  const validateStory = () => run(
    () => actions.validateStory(),
    "Story Quality 检查完成",
    (result) => setStoryQuality(result),
  );

  const goNext = () => {
    const next = scriptSteps[currentStep + 1];
    if (next) setStep(next[0]);
  };

  return <div className="module-page script-page">
    <PageHeader eyebrow="Script Pipeline" title="剧本工作台" description="把故事规则逐步落成剧集矩阵、场景剧本和可生成的分镜。每一步都能保存，随时继续。" action={<div className="script-header-meta"><span>{episode?.id} {episode?.title}</span><strong>{currentStep + 1} / {scriptSteps.length}</strong></div>} />
    <nav className="script-stepper" aria-label="剧本生产流程">{scriptSteps.map(([id, label, hint], index) => <button className={step === id ? "is-active" : index < currentStep ? "is-done" : ""} key={id} type="button" onClick={() => setStep(id)}><i>{index < currentStep ? <Check size={13} weight="bold" /> : index + 1}</i><span><strong>{label}</strong><small>{hint}</small></span>{index < scriptSteps.length - 1 && <ArrowRight size={15} />}</button>)}</nav>
    <div className="script-toolbar"><label>当前剧集<select value={episodeId} onChange={(event) => { setEpisodeId(event.target.value); actions.updateProject({ currentEpisodeId: event.target.value }); }}><option value="">选择剧集</option>{project.episodes.map((item) => <option key={item.id} value={item.id}>{item.id}　{item.title}</option>)}</select></label><span className="script-save-state">{busy ? "处理中…" : notice || "所有修改都保存到项目数据库"}</span><button type="button" onClick={() => actions.openEpisode(episodeId)}>进入分镜 <ArrowRight size={15} /></button></div>
    {step === "bible" && <section className="module-section agent-command-card">
      <div className="section-heading"><div><h2>Story Engine</h2><p>输入创意、小说梗概或现有故事，让系统生成 Story Bible、人物设定、场景设计和全剧分集结构。</p></div><Sparkle size={22} weight="duotone" /></div>
      <label className="agent-goal-field"><span>创作原料</span><textarea value={sourceDraft} onChange={(event) => setSourceDraft(event.target.value)} placeholder="可以输入一句创意、小说梗概、原著摘要或现有剧本。留空时会基于当前 Story Bible 继续完善。" /></label>
      <div className="agent-command-footer"><span>结构化结果会直接写入项目数据库；后续场景剧本、人物资产、分镜和配音都引用同一套稳定 ID。</span><div className="agent-command-actions"><button type="button" onClick={validateStory} disabled={busy}>质量检查</button><button className="primary-action" type="button" onClick={developStory} disabled={busy}><Sparkle size={16} />AI 全剧策划</button></div></div>
      {storyQuality && <div className="agent-plan-list">{(storyQuality.gates || []).map((gate, index) => <div className={`agent-plan-step ${gate.status === "pass" ? "done" : gate.status === "fail" ? "failed" : "pending"}`} key={gate.id}><i>{gate.status === "pass" ? <Check size={14} weight="bold" /> : gate.status === "fail" ? "!" : index + 1}</i><div><strong>{gate.id}</strong><small>{gate.message}</small></div><em>{gate.status}</em></div>)}</div>}
    </section>}
    {step === "bible" && <div className="story-layout script-stage"><section className="module-section story-form"><div className="section-heading script-section-heading"><div><h2>先固定故事边界</h2><p>后面的矩阵、场景和镜头都从这里继承。</p></div></div>{[["logline", "一句话梗概"], ["coreConflict", "核心冲突"], ["mainLine", "故事主线"], ["theme", "主题"], ["ending", "最终结局"], ["world", "世界观"], ["style", "视觉风格"]].map(([field, label]) => <label key={field}><span>{label}</span><textarea value={project.storyBible[field]} onChange={(event) => actions.updateStory(field, event.target.value)} /></label>)}</section><section className="module-section rules-panel"><div className="section-heading"><div><h2>不可违反的规则</h2><p>生成时自动带入。</p></div></div><div className="rule-list">{project.storyBible.rules.map((rule, index) => <div key={`${rule}-${index}`}><span>{index + 1}</span><p>{rule}</p><button type="button" aria-label="删除规则" onClick={() => actions.removeRule(index)}>×</button></div>)}</div><form onSubmit={(event) => { event.preventDefault(); const input = event.currentTarget.elements.rule.value; actions.addRule(input); event.currentTarget.reset(); }}><input name="rule" placeholder="例如：角色在第 08 集前不能知道真相" /><button type="submit"><Plus size={16} />添加规则</button></form></section></div>}
    {step === "matrix" && <div className="script-grid script-stage"><aside className="module-section script-episode-list"><div className="section-heading"><div><h2>剧集列表</h2><p>先明确每集要推进什么。</p></div></div>{project.episodes.map((item) => <button className={item.id === episodeId ? "is-active" : ""} key={item.id} type="button" onClick={() => setEpisodeId(item.id)}><strong>{item.id}</strong><span>{item.title}</span><em>{item.status}</em></button>)}</aside><section className="module-section script-editor"><div className="section-heading"><div><h2>{episode?.id} 剧集矩阵</h2><p>用五个问题锁定本集节奏，避免直接跳到镜头。</p></div><div className="script-editor-actions"><button type="button" onClick={saveMatrix} disabled={busy}>保存</button><button className="primary-action" type="button" onClick={generateMatrix} disabled={busy}><Sparkle size={16} />生成矩阵</button></div></div><div className="matrix-form">{[["hook", "开场钩子", "观众为什么要继续看？"], ["coreEvent", "核心事件", "本集真正发生了什么？"], ["payoff", "情绪回收", "这一集给观众什么兑现？"], ["twist", "转折线索", "哪里改变了观众的判断？"], ["endingHook", "结尾钩子", "下一集从哪个问题开始？"]].map(([field, label, placeholder]) => <label key={field}><span>{label}</span><textarea value={matrix[field]} placeholder={placeholder} onChange={(event) => setMatrix((current) => ({ ...current, [field]: event.target.value }))} /></label>)}</div></section></div>}
    {step === "scene" && <div className="script-grid script-stage"><aside className="module-section script-episode-list scene-list"><div className="section-heading"><div><h2>场景列表</h2><p>{episode?.id} 的可拍场景。</p></div><button type="button" onClick={createScene}><Plus size={15} />新增</button></div>{scenes.map((item) => <button className={item.id === sceneId ? "is-active" : ""} key={item.id} type="button" onClick={() => setSceneId(item.id)}><strong>场景 {item.order}</strong><span>{item.title}</span><em>{item.script?.beats?.length ? "已写" : "待写"}</em></button>)}{!scenes.length && <div className="script-empty"><FileText size={20} /><strong>还没有场景</strong><span>从本集矩阵创建第一个可拍场景。</span><button type="button" onClick={createScene}>创建场景</button></div>}</aside><section className="module-section script-editor"><div className="section-heading"><div><h2>{scene ? scene.title : "场景剧本"}</h2><p>先说清楚场景目的，再生成对白和动作节拍。</p></div>{scene && <div className="script-editor-actions"><button type="button" onClick={saveScene} disabled={busy}>保存场景</button><button className="primary-action" type="button" onClick={generateScript} disabled={busy}><Sparkle size={16} />生成剧本</button></div>}</div>{scene ? <div className="scene-script-form"><div className="scene-meta-form"><label>场景名称<input value={sceneDraft.title} onChange={(event) => setSceneDraft((current) => ({ ...current, title: event.target.value }))} /></label><label>时间<select value={sceneDraft.timeOfDay} onChange={(event) => setSceneDraft((current) => ({ ...current, timeOfDay: event.target.value }))}><option value="">未设定</option><option>白天</option><option>夜晚</option><option>黄昏</option></select></label></div><label>场景目的<textarea value={sceneDraft.purpose} onChange={(event) => setSceneDraft((current) => ({ ...current, purpose: event.target.value }))} placeholder="这个场景结束时，人物关系发生什么变化？" /></label><label>场景摘要<textarea value={sceneDraft.summary} onChange={(event) => setSceneDraft((current) => ({ ...current, summary: event.target.value }))} placeholder="用 2-3 句话描述可拍内容" /></label><label className="beat-editor">动作与对白节拍<textarea value={scriptDraft} onChange={(event) => setScriptDraft(event.target.value)} placeholder="每行一个节拍，例如：\n林泽走到天台边，停下。\n苏晴：你真的要走吗？\n林泽没有回头。" /><small>每行会成为一个动作或对白节拍，生成后可继续修改。</small></label></div> : <div className="script-empty large"><FileText size={25} /><strong>从左侧创建场景</strong><span>场景是剧集矩阵进入分镜生产的桥梁。</span></div>}</section></div>}
    {step === "breakdown" && <div className="module-section script-breakdown script-stage"><div className="section-heading"><div><h2>{scene ? `${scene.title} · 分镜拆解` : "分镜拆解"}</h2><p>把场景节拍转成镜头、景别和生成任务。</p></div><div className="script-editor-actions">{scene && <button className="primary-action" type="button" onClick={generateBreakdown} disabled={busy}><Sparkle size={16} />生成分镜拆解</button>}</div></div>{scene ? <><div className="breakdown-meta"><span><strong>{scene.id}</strong> {scene.purpose || "尚未填写场景目的"}</span><span>{sceneShots.length} 个镜头</span></div>{sceneShots.length ? <div className="breakdown-list">{sceneShots.map((shot, index) => <div key={shot.id}><span className="breakdown-index">{String(index + 1).padStart(2, "0")}</span><img src={shot.image} alt="" /><div><strong>{shot.description}</strong><small>{shot.dialogue || "无对白"}</small></div><em>{shot.size}</em><span>{shot.duration}s</span><span className={`task-status ${shot.status}`}>{shot.status}</span><button type="button" onClick={() => actions.openEpisode(episodeId)}>编辑<ArrowRight size={14} /></button></div>)}</div> : <div className="script-empty large"><Sparkle size={25} /><strong>还没有分镜拆解</strong><span>完成场景剧本后，点击右上角生成第一版镜头。</span></div>}</> : <div className="script-empty large"><FileText size={25} /><strong>先选择一个场景</strong><span>回到场景剧本步骤创建或选择场景。</span></div>}</div>}
    <div className="script-footer"><span>{notice || "流程建议：先完成矩阵，再进入场景和分镜。"}</span><div>{currentStep > 0 && <button type="button" onClick={() => setStep(scriptSteps[currentStep - 1][0])}>上一步</button>}{currentStep < scriptSteps.length - 1 && <button className="primary-action" type="button" onClick={goNext}>下一步 <ArrowRight size={15} /></button>}</div></div>
  </div>;
}

function EpisodesPage({ project, onOpenEpisode }) {
  return <div className="module-page"><PageHeader eyebrow="Episodes" title="剧集管理" description="查看每一集的故事状态、场景与镜头进度。" />
    <section className="module-section episode-table"><div className="episode-table-head"><span>剧集</span><span>标题 / 钩子</span><span>场景</span><span>镜头</span><span>状态</span><span /></div>{project.episodes.map((episode) => <div className={episode.id === project.currentEpisodeId ? "is-current" : ""} key={episode.id}><strong>{episode.id}</strong><span><b>{episode.title}</b><small>{episode.hook}</small></span><span>{episode.scenes || "--"}</span><span>{episode.shots || "--"}</span><em className={`episode-status ${episode.status}`}>{episode.status}</em><button type="button" onClick={() => onOpenEpisode(episode.id)}>进入分镜<ArrowRight size={15} /></button></div>)}</section>
  </div>;
}

function AssetGenerationPage({ project, actions }) {
  const [assetType, setAssetType] = useState("characters");
  const [name, setName] = useState("林泽");
  const [description, setDescription] = useState("28岁，黑发，克制冷静，创业者，眼神坚定但带着压抑的情绪。");
  const [style, setStyle] = useState("电影感写实");
  const [negativePrompt, setNegativePrompt] = useState("避免卡通感、过度磨皮、畸形手指、文字水印");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [generated, setGenerated] = useState(null);

  const config = {
    characters: { label: "人物图", meta: "角色参考", placeholder: "年龄、外貌、气质、身份、服装…", defaultName: "林泽", defaultDescription: "28岁，黑发，克制冷静，创业者，眼神坚定但带着压抑的情绪。" },
    locations: { label: "场景图", meta: "场景参考", placeholder: "时间、空间、光线、材质、氛围…", defaultName: "城市天台", defaultDescription: "夜晚城市天台，江面反光，远处高楼灯光，冷蓝色电影感，适合两个人对峙。" },
  };
  const currentConfig = config[assetType];
  const assets = project.assets[assetType] || [];

  useEffect(() => {
    setName(currentConfig.defaultName);
    setDescription(currentConfig.defaultDescription);
    setGenerated(null);
    setNotice("");
  }, [assetType]);

  const generate = async () => {
    if (busy) return;
    setBusy(true);
    setNotice("");
    try {
      const prompt = `${name}，${description}。${style}，短剧制作参考图，构图清晰，主体明确。负面约束：${negativePrompt}`;
      const response = await actions.generateAsset(assetType, {
        name,
        description,
        prompt,
        style,
        negativePrompt,
        meta: currentConfig.meta,
        role: assetType === "characters" ? "主要角色" : undefined,
        status: "已生成",
      }, (completedAsset) => {
        if (completedAsset) {
          setGenerated(completedAsset);
          setNotice(`已生成 ${completedAsset.id}，预计消耗 ¥${Number(response.cost || 0.18).toFixed(2)}`);
        }
      }, (failedTask) => {
        setGenerated((current) => current ? { ...current, image: null, status: "生成失败" } : current);
        setNotice(`生成失败：${failedTask?.error || "未配置真实图片生成 API"}`);
      });
      setGenerated(response.asset);
      setNotice(`已提交 ${response.asset.id}，正在等待真实图片接口返回…`);
    } catch (error) {
      setNotice(error?.message || "生成失败，请检查 FastAPI 连接");
    } finally {
      setBusy(false);
    }
  };

  return <div className="module-page asset-generator-page">
    <PageHeader eyebrow="Asset Generator" title="人物与场景生图" description="先建立可复用的视觉资产，后续 Agent 和镜头生成会统一引用它们。" action={<span className={`agent-runtime ${actions.backendStatus}`}>{actions.backendStatus !== "online" ? "等待 API" : actions.providerInfo?.mode === "remote" ? "Image API 已连接" : "未配置真实图片 API"}</span>} />
    <div className="asset-generator-layout">
      <section className="module-section asset-generator-form">
        <div className="section-heading"><div><h2>生成设置</h2><p>把文字描述变成项目资产。</p></div><Sparkle size={23} weight="duotone" /></div>
        <div className="asset-type-switch"><button className={assetType === "characters" ? "is-active" : ""} type="button" onClick={() => setAssetType("characters")}><span className="asset-type-icon character"><Images size={18} /></span><span><strong>人物图</strong><small>统一角色外观</small></span></button><button className={assetType === "locations" ? "is-active" : ""} type="button" onClick={() => setAssetType("locations")}><span className="asset-type-icon location"><FilmStrip size={18} /></span><span><strong>场景图</strong><small>建立空间与氛围</small></span></button></div>
        <div className="asset-generator-fields"><label>资产名称<input value={name} onChange={(event) => setName(event.target.value)} placeholder={currentConfig.defaultName} /></label><label>描述<span className="field-hint">{currentConfig.placeholder}</span><textarea value={description} onChange={(event) => setDescription(event.target.value)} /></label><label>视觉风格<select value={style} onChange={(event) => setStyle(event.target.value)}><option>电影感写实</option><option>短剧清晰人物</option><option>低饱和都市</option><option>暖调生活感</option></select></label><label>负面约束<textarea className="compact" value={negativePrompt} onChange={(event) => setNegativePrompt(event.target.value)} /></label></div>
        <div className="asset-generator-footer"><span>{actions.backendStatus === "online" ? (actions.providerInfo?.mode === "remote" ? "生成结果会自动保存到素材库。" : "未配置真实图片 API，本次测试会记录失败，不会生成预设图片。") : "FastAPI 未连接，暂时不能生成。"}</span><button className="primary-action" type="button" onClick={generate} disabled={busy || actions.backendStatus !== "online"}><Sparkle size={16} />{busy ? "生成中…" : `生成${currentConfig.label}`}</button></div>
      </section>
      <section className="module-section asset-generator-preview"><div className="section-heading"><div><h2>{generated ? generated.name : "生成预览"}</h2><p>{generated ? (generated.status === "生成失败" ? "未生成图片，请修正接口配置后在任务中心重试。" : generated.status === "已生成" ? "已写入项目资产，可在素材库继续编辑。" : "任务已提交，等待真实图片接口返回。") : "生成后的参考图会显示在这里。"}</p></div>{generated && <span className={`asset-generated-pill ${generated.status === "生成失败" ? "error" : ""}`}>{generated.status || "生成中"}</span>}</div>{generated?.image ? <div className="asset-generated-image"><img src={generated.image} alt={generated.name} /></div> : <div className="asset-preview-empty"><Images size={30} /><strong>{generated?.status === "生成失败" ? "没有生成图片" : "等待生成结果"}</strong><span>{generated?.status === "生成失败" ? "任务中心已记录失败原因，不会使用预设图片冒充结果。" : "建议先生成一版，再根据连续性补充描述。"}</span></div>}{notice && <div className={`asset-generator-notice ${notice.includes("失败") || notice.includes("错误") ? "error" : ""}`}>{notice}</div>}{generated && <div className="asset-generated-meta"><div><span>资产编号</span><strong>{generated.id}</strong></div><div><span>类型</span><strong>{currentConfig.meta}</strong></div><div><span>状态</span><strong>{generated.status}</strong></div></div>}</section>
    </div>
    <section className="module-section asset-recent-section"><div className="section-heading"><div><h2>已有{currentConfig.label}</h2><p>生成后会自动加入这里，并可以被分镜和 Agent 复用。</p></div><button type="button" onClick={() => actions.navigate("素材库")}>打开素材库 <ArrowRight size={15} /></button></div><div className="asset-recent-grid">{assets.length ? assets.slice(-6).reverse().map((asset) => <article key={asset.id}>{asset.image ? <img src={asset.image} alt={asset.name} /> : <div className="asset-media-empty">未生成</div>}<div><span>{asset.id}</span><strong>{asset.name}</strong><small>{asset.meta || currentConfig.meta}</small></div></article>) : <div className="asset-preview-empty small"><Images size={21} /><span>还没有资产</span></div>}</div></section>
  </div>;
}

function CharacterEnginePanel({ character, actions }) {
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  if (!character) return <div className="character-engine-empty">选择一个角色开始建立 Identity。</div>;
  const run = async (operation, success) => {
    setBusy(true);
    setNotice("");
    try {
      await operation();
      setNotice(success);
    } catch (error) {
      setNotice(error?.message || "操作失败");
    } finally {
      setBusy(false);
    }
  };
  const anchors = character.identityAnchors || {};
  const references = character.references || [];
  const looks = character.looks || [];
  return <section className="character-engine-panel">
    <div className="character-engine-head"><div><span>{character.id} · Character Asset Engine</span><h2>{character.name}</h2><p>{character.description || "还没有角色描述"}</p></div><em className={character.identityLocked ? "locked" : "draft"}>{character.identityLocked ? "Identity Locked" : "Draft"}</em></div>
    <div className="character-engine-actions"><button type="button" onClick={() => run(() => actions.extractCharacterAnchors(character.id), "Identity Anchors 已更新")} disabled={busy}><Sparkle size={15} />提取 Anchors</button><button type="button" onClick={() => run(() => actions.generateCharacterCandidates(character.id, { count: 4 }), "4 张候选图已进入任务队列")} disabled={busy}><Images size={15} />生成 4 候选</button><button type="button" onClick={() => run(() => actions.generateCharacterMasterSheet(character.id, {}), "Master Sheet 已进入任务队列")} disabled={busy || !character.canonicalReferenceId}>生成 Master Sheet</button>{character.identityLocked ? <button type="button" onClick={() => run(() => actions.unlockCharacter(character.id), "Identity 已解锁")} disabled={busy}>解锁</button> : <button className="primary-action" type="button" onClick={() => run(() => actions.lockCharacter(character.id), "Identity 已锁定")} disabled={busy || !character.canonicalReferenceId}>锁定 Identity</button>}</div>
    {notice && <div className="character-engine-notice">{notice}</div>}
    <div className="character-engine-stats"><div><span>Look</span><strong>{character.lookCount || looks.length}</strong></div><div><span>Approved Ref</span><strong>{character.approvedReferenceCount || 0}</strong></div><div><span>Used in shots</span><strong>{character.usageCount || 0}</strong></div><div><span>Canonical</span><strong>{character.canonicalReferenceId ? "已选" : "待选"}</strong></div></div>
    <div className="character-engine-section"><div className="section-heading"><div><h3>Identity Anchors</h3><p>稳定身份，不随服装和剧情状态改变。</p></div></div><div className="anchor-chips">{[anchors.hair, anchors.faceShape, anchors.bodySilhouette, ...(anchors.uniqueMarks || [])].filter(Boolean).map((item, index) => <span key={`${item}-${index}`}>{item}</span>)}</div>{!Object.keys(anchors).length && <small className="character-engine-muted">先提取 Anchors，再让用户确认脸型、独特标记和四视图细节。</small>}</div>
    <div className="character-engine-section"><div className="section-heading"><div><h3>Looks <span>{looks.length}</span></h3><p>服装、妆容、伤痕和天气等可变状态。</p></div><button type="button" onClick={() => run(() => actions.createCharacterLook(character.id, { name: `新造型 ${looks.length + 1}`, description: "补充该造型与身份的差异。", differences: { wardrobe: "待填写" } }), "已添加新造型")} disabled={busy}><Plus size={14} />添加</button></div><div className="look-list">{looks.map((look) => <div key={look.id}><strong>{look.name}</strong><span>{look.description || "未填写差异"}</span><em>{look.status}</em></div>)}</div></div>
    <div className="character-engine-section"><div className="section-heading"><div><h3>References <span>{references.length}</span></h3><p>只有 approved 参考图会进入分镜生成请求。</p></div></div><div className="reference-grid">{references.map((reference) => <article className={reference.id === character.canonicalReferenceId ? "canonical" : ""} key={reference.id}>{reference.image ? <img src={reference.image} alt="" /> : <div className="asset-media-empty">未生成</div>}<div><strong>{reference.referenceType}</strong><span>{reference.lifecycleStatus}</span></div>{reference.lifecycleStatus === "generated" && <div className="reference-actions"><button type="button" onClick={() => run(() => actions.reviewCharacterReference(reference.id, true), "参考图已审核")}>通过</button><button type="button" onClick={() => run(() => actions.reviewCharacterReference(reference.id, false), "参考图已拒绝")}>拒绝</button><button type="button" onClick={() => run(() => actions.setCharacterCanonical(character.id, reference.id), "已设为 Canonical")}>设为 Canonical</button></div>}{reference.lifecycleStatus === "approved" && reference.id !== character.canonicalReferenceId && <button type="button" className="reference-canonical-button" onClick={() => run(() => actions.setCharacterCanonical(character.id, reference.id), "已设为 Canonical")}>设为 Canonical</button>}{reference.id === character.canonicalReferenceId && <em className="canonical-label">Canonical</em>}</article>)}{!references.length && <small className="character-engine-muted">候选图生成后会在这里出现。</small>}</div></div>
  </section>;
}

function AssetsPage({ project, onAddAsset, onUpdateAsset, actions }) {
  const [tab, setTab] = useState("characters");
  const [selectedCharacterId, setSelectedCharacterId] = useState(project.assets.characters[0]?.id);
  const config = { characters: ["角色", "新增角色"], locations: ["场景", "新增场景"], props: ["道具", "新增道具"] };
  const items = project.assets[tab];
  return <div className="module-page"><PageHeader eyebrow="Asset System" title="项目资产库" description={tab === "characters" ? "先确认 Identity，再管理多个 Look；已审核 Reference 才能进入生产。" : "角色、场景和道具在所有镜头中保持统一引用。"} action={<button className="primary-action" type="button" onClick={() => onAddAsset(tab)}><Plus size={18} />{config[tab][1]}</button>} />
    <div className="page-tabs">{Object.entries(config).map(([key, [label]]) => <button className={tab === key ? "is-active" : ""} key={key} onClick={() => setTab(key)} type="button">{label}<span>{project.assets[key].length}</span></button>)}</div>
    {tab === "characters" ? <div className="character-engine-layout"><div className="character-list">{items.map((item) => <button className={selectedCharacterId === item.id ? "is-active" : ""} key={item.id} type="button" onClick={() => setSelectedCharacterId(item.id)}>{item.image ? <img src={item.image} alt="" /> : <div className="asset-media-empty">未生成</div>}<span><strong>{item.name}</strong><small>{item.id} · {item.role || item.meta || "角色"}</small><em>{item.identityLocked ? "Locked" : "Draft"}</em></span><ArrowRight size={16} /></button>)}</div><CharacterEnginePanel character={items.find((item) => item.id === selectedCharacterId) || items[0]} actions={actions} /></div> : <div className="asset-grid">{items.map((item) => <article className="asset-card" key={item.id}>{item.image ? <img src={item.image} alt="" /> : <div className="asset-media-empty">未生成</div>}<div><span>{item.id}</span><input value={item.name} onChange={(event) => onUpdateAsset(tab, item.id, { name: event.target.value })} /><small>{item.meta}</small><textarea value={item.description} onChange={(event) => onUpdateAsset(tab, item.id, { description: event.target.value })} /><em>{item.status}</em></div></article>)}</div>}
  </div>;
}

function GenerationPage({ project, onRetry, onCancel, onNavigate }) {
  return <div className="module-page"><PageHeader eyebrow="Generation Center" title="统一任务中心" description="图片、视频、音频、Agent 和 MP4 渲染都从这里追踪；每条任务都带有 Provider、模型、进度和错误记录。" action={<button className="primary-action" type="button" onClick={() => onNavigate("分镜")}><Sparkle size={18} />选择镜头生成</button>} />
    <div className="task-summary"><div><span>运行中</span><strong>{project.tasks.filter((task) => task.status === "Running").length}</strong></div><div><span>已成功</span><strong>{project.tasks.filter((task) => task.status === "Success").length}</strong></div><div><span>失败/阻塞</span><strong>{project.tasks.filter((task) => task.status === "Failed" || task.status === "Blocked").length}</strong></div><div><span>任务成本</span><strong>¥{project.tasks.reduce((sum, task) => sum + task.cost, 0).toFixed(2)}</strong></div></div>
    <section className="module-section task-table"><div className="task-table-head"><span>任务</span><span>目标</span><span>类型</span><span>模型</span><span>状态</span><span>成本</span><span>操作</span></div>{project.tasks.map((task) => <div key={task.id}><code>{task.id}</code><strong>{task.shotId || task.targetId || "—"}</strong><span>{task.type}{task.provider ? ` · ${task.provider}` : ""}</span><span>{task.model}</span><em className={`task-status ${task.status}`}>{task.status}{task.error && <small title={task.error}>{task.error}</small>}</em><span>¥{task.cost.toFixed(2)}</span><span className="table-actions">{task.targetType === "render" ? <button type="button" onClick={() => onNavigate("时间线")}>查看</button> : <>{task.status === "Failed" || task.status === "Cancelled" ? <button type="button" onClick={() => onRetry(task.id)}>重试</button> : null}{task.status === "Running" ? <button type="button" onClick={() => onCancel(task.id)}>取消</button> : null}</>}</span></div>)}</section>
  </div>;
}

function AudioPage({ project, actions }) {
  const [episodeId, setEpisodeId] = useState(() => project.audio?.dialogueLines?.[0]?.episodeId || project.currentEpisodeId);
  const [sceneId, setSceneId] = useState(project.currentScene?.id || null);
  const [scenes, setScenes] = useState([]);
  const [selectedLineId, setSelectedLineId] = useState(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [emotion, setEmotion] = useState("克制");
  const [speed, setSpeed] = useState("1");

  useEffect(() => {
    let active = true;
    actions.loadScenes(episodeId).then((items) => {
      if (!active) return;
      setScenes(items);
      setSceneId((current) => items.some((item) => item.id === current) ? current : items[0]?.id || null);
    }).catch(() => active && setNotice("场景读取失败，请检查 FastAPI"));
    return () => { active = false; };
  }, [episodeId]);

  const lines = (project.audio?.dialogueLines || []).filter((line) => line.episodeId === episodeId && (!sceneId || line.sceneId === sceneId));
  const selectedLine = lines.find((line) => line.id === selectedLineId) || lines[0];
  const selectedProfile = selectedLine?.voiceProfile;
  const episode = project.episodes.find((item) => item.id === episodeId);

  useEffect(() => {
    if (selectedLine) {
      setSelectedLineId(selectedLine.id);
      setEmotion(selectedLine.performance?.emotion || "克制");
      setSpeed(String(selectedLine.performance?.speed || 1));
    }
  }, [selectedLine?.id]);

  const run = async (operation, message) => {
    setBusy(true);
    setNotice("");
    try {
      await operation();
      setNotice(message);
    } catch (error) {
      setNotice(error?.message || "操作失败，请稍后重试");
    } finally {
      setBusy(false);
    }
  };

  const activeTake = selectedLine?.activeTake || selectedLine?.takes?.[0];
  return <div className="module-page audio-page">
    <PageHeader eyebrow="Audio Engine" title="声音工作台" description="从场景台词开始，选择稳定声音身份，生成逐句 Take，完成 QC 后再放进独立音频轨道。" action={<span className={`audio-runtime ${actions.backendStatus}`}>{actions.backendStatus === "online" ? "Audio API 已连接" : "等待 API"}</span>} />
    <div className="audio-toolbar module-section">
      <label>剧集<select value={episodeId} onChange={(event) => { setEpisodeId(event.target.value); actions.updateProject({ currentEpisodeId: event.target.value }); }}><option value="">选择剧集</option>{project.episodes.map((item) => <option key={item.id} value={item.id}>{item.id} · {item.title}</option>)}</select></label>
      <label>场景<select value={sceneId || ""} onChange={(event) => setSceneId(event.target.value)}><option value="">全部场景</option>{scenes.map((item) => <option key={item.id} value={item.id}>{item.id} · {item.title}</option>)}</select></label>
      <div className="audio-toolbar-actions"><button type="button" onClick={() => run(() => actions.extractDialogueLines(sceneId), "已从镜头对白提取台词")} disabled={!sceneId || busy}><SpeakerHigh size={15} />提取台词</button><button className="primary-action" type="button" onClick={() => run(() => actions.generateEpisodeDialogue(episodeId, { sceneId }), "本集音频任务已创建")} disabled={!lines.length || busy}><Sparkle size={15} />生成本集音频</button></div>
    </div>
    {notice && <div className="audio-notice">{notice}</div>}
    <div className="audio-workspace">
      <section className="module-section audio-lines-panel"><div className="section-heading"><div><h2>{episode?.id} 台词行</h2><p>{lines.length} 条对白 · 每条都可以独立重生成和审核</p></div><span className="audio-count">{project.audio?.counts?.ready || 0} 已就绪</span></div>{!lines.length ? <div className="audio-empty"><SpeakerHigh size={26} /><strong>还没有提取台词</strong><span>先选择一个有镜头对白的场景。</span></div> : <div className="audio-line-list">{lines.map((line) => <button type="button" key={line.id} className={selectedLine?.id === line.id ? "is-active" : ""} onClick={() => setSelectedLineId(line.id)}><span className="audio-line-index">{String(line.order + 1).padStart(2, "0")}</span><span className="audio-line-copy"><strong>{line.characterName}</strong><em>{line.text}</em><small>{line.shotId || "场景台词"} · 目标 {Math.round((line.targetDurationMs || 0) / 1000)}s</small></span><span className={`audio-line-status ${line.status}`}>{line.activeTake ? "可用" : line.status === "queued" ? "排队" : "待生成"}</span></button>)}</div>}</section>
      <section className="module-section audio-inspector"><div className="section-heading"><div><h2>{selectedLine ? selectedLine.characterName : "台词检查"}</h2><p>{selectedLine ? selectedLine.id : "选择左侧台词开始"}</p></div>{selectedLine?.stale && <span className="audio-stale">需要重生成</span>}</div>{selectedLine ? <><div className="audio-text-card"><span>Dialogue Line</span><p>{selectedLine.text}</p><small>目标时长 {selectedLine.targetDurationMs || "未设置"} ms · {selectedLine.language}</small></div><div className="audio-inspector-block"><div className="section-heading"><div><h3>Voice Identity</h3><p>身份与表现分开管理</p></div>{selectedProfile?.locked && <span className="audio-lock">Locked</span>}</div>{selectedProfile ? <div className="audio-profile-card"><div><strong>{selectedProfile.name}</strong><small>{selectedProfile.providerType} · 权利：{selectedProfile.consentStatus}</small></div>{selectedProfile.locked ? <button type="button" onClick={() => run(() => actions.unlockVoiceProfile(selectedProfile.id), "声音档案已解锁")} disabled={busy}>解锁</button> : <><button type="button" onClick={() => run(() => actions.patchVoiceProfile(selectedProfile.id, { consentStatus: "user_owned" }), "已登记声音权利")} disabled={busy || selectedProfile.consentStatus === "user_owned"}>登记自有</button><button type="button" onClick={() => run(() => actions.lockVoiceProfile(selectedProfile.id), "声音档案已锁定")} disabled={busy || !["user_owned", "licensed", "approved"].includes(selectedProfile.consentStatus)}>锁定</button></>}</div> : <p className="audio-muted">该角色还没有声音档案，请先在素材库的角色页创建。</p>}</div><div className="audio-inspector-block"><div className="section-heading"><div><h3>AI Voice Direction</h3><p>情绪、速度和交付指令属于当前台词</p></div><button type="button" onClick={() => run(() => actions.directPerformance(selectedLine.id, { emotion, speed: Number(speed) }), "Voice Direction 已更新")} disabled={busy}>生成</button></div><div className="audio-control-grid"><label>情绪<select value={emotion} onChange={(event) => setEmotion(event.target.value)}>{["克制", "坚定", "惊讶", "悲伤", "愤怒", "温柔"].map((item) => <option key={item}>{item}</option>)}</select></label><label>速度<select value={speed} onChange={(event) => setSpeed(event.target.value)}><option value="0.85">0.85×</option><option value="1">1.0×</option><option value="1.15">1.15×</option></select></label></div><p className="audio-delivery">{selectedLine.performance?.deliveryInstruction || "先稳住情绪，再把关键词说清楚"}</p></div><div className="audio-inspector-block"><div className="section-heading"><div><h3>Voice Takes <span>{selectedLine.takes?.length || 0}</span></h3><p>Take 是不可变版本，QC 通过后才能进入时间线</p></div><button className="primary-action" type="button" onClick={() => run(() => actions.generateDialogue(selectedLine.id, {}), "音频已进入任务队列")} disabled={busy || !selectedProfile}>生成一版</button></div>{selectedLine.takes?.length ? <div className="audio-take-list">{selectedLine.takes.map((take) => <div className="audio-take-row" key={take.id}><div><strong>{take.id}</strong><small>{take.provider} · {take.durationMs ? `${(take.durationMs / 1000).toFixed(1)}s` : "处理中"} · QC {take.qcScore ?? "--"}</small></div><div><button type="button" onClick={() => run(() => actions.runTakeQC(take.id), "QC 已完成")} disabled={busy || take.status !== "success"}>QC</button><button type="button" onClick={() => run(() => actions.activateTake(take.id), "已启用该 Take")} disabled={busy || take.status !== "success"}>{take.active ? "已启用" : "启用"}</button><button type="button" onClick={() => run(() => actions.createAudioClip({ takeId: take.id, episodeId, sceneId, timelineStartMs: selectedLine.startOffsetMs || 0, trackType: "dialogue" }), "已加入 Dialogue 轨道")} disabled={busy || take.status !== "success"}>入轨</button></div></div>)}</div> : <p className="audio-muted">还没有版本。生成后会显示音频文件、QC 和入轨操作。</p>}{activeTake?.qcStatus === "pass" && <div className="audio-qc-pass"><CheckCircle size={15} />QC 通过，可以进入时间线</div>}</div></> : <div className="audio-empty"><SpeakerHigh size={26} /><strong>选择一条台词</strong><span>右侧会显示声音身份、表现方向和 Take。</span></div>}</section>
    </div>
  </div>;
}

function TimelineClipEditor({ clip, onSave, onDelete }) {
  const [draft, setDraft] = useState({ timelineStartMs: clip.timelineStartMs || 0, durationMs: clip.durationMs || 0, gainDb: clip.gainDb || 0 });
  useEffect(() => setDraft({ timelineStartMs: clip.timelineStartMs || 0, durationMs: clip.durationMs || 0, gainDb: clip.gainDb || 0 }), [clip.id, clip.timelineStartMs, clip.durationMs, clip.gainDb]);
  const update = (key, value) => setDraft((current) => ({ ...current, [key]: value }));
  return <article className="timeline-clip-editor"><div><strong>{clip.linkedDialogueLineId || clip.id}</strong><small>{clip.trackType} · {clip.stale ? "需要重审" : "已入轨"}</small></div><label>起点 ms<input type="number" min="0" value={draft.timelineStartMs} onChange={(event) => update("timelineStartMs", Number(event.target.value))} /></label><label>时长 ms<input type="number" min="0" value={draft.durationMs} onChange={(event) => update("durationMs", Number(event.target.value))} /></label><label>增益 dB<input type="number" step="0.5" value={draft.gainDb} onChange={(event) => update("gainDb", Number(event.target.value))} /></label><button type="button" onClick={() => onSave(clip.id, draft)}>保存</button><button type="button" onClick={() => onDelete(clip.id)}>删除</button></article>;
}

function TimelineVideoClipEditor({ clip, onSave, onDelete }) {
  const [draft, setDraft] = useState({ timelineStartMs: clip.timelineStartMs || 0, durationMs: clip.durationMs || 0 });
  useEffect(() => setDraft({ timelineStartMs: clip.timelineStartMs || 0, durationMs: clip.durationMs || 0 }), [clip.id, clip.timelineStartMs, clip.durationMs]);
  const update = (key, value) => setDraft((current) => ({ ...current, [key]: value }));
  return <article className="timeline-clip-editor video-clip-editor"><div><strong>{clip.shotId}</strong><small>{clip.description || "视频镜头"} · {clip.stale ? "需要重审" : "可编辑"}</small></div><label>起点 ms<input type="number" min="0" value={draft.timelineStartMs} onChange={(event) => update("timelineStartMs", Number(event.target.value))} /></label><label>时长 ms<input type="number" min="1" value={draft.durationMs} onChange={(event) => update("durationMs", Number(event.target.value))} /></label><button type="button" onClick={() => onSave(clip.id, draft)}>保存</button><button type="button" onClick={() => onDelete(clip.id)}>移除</button></article>;
}

function TimelinePage({ project, actions }) {
  const [episodeId, setEpisodeId] = useState(project.currentEpisodeId);
  useEffect(() => setEpisodeId(project.currentEpisodeId), [project.currentEpisodeId]);
  const shots = project.shots.filter((shot) => shot.episodeId === episodeId);
  const videoClips = (project.timeline?.videoClips || []).filter((clip) => clip.episodeId === episodeId);
  const omittedShots = shots.filter((shot) => !videoClips.some((clip) => clip.shotId === shot.id));
  const total = Math.max(shots.reduce((sum, shot) => sum + shot.duration, 0) * 1000, ...videoClips.map((clip) => (clip.timelineStartMs || 0) + (clip.durationMs || 0))) / 1000 || 1;
  const audioClips = (project.audio?.clips || []).filter((clip) => clip.episodeId === episodeId);
  const audioLines = (project.audio?.dialogueLines || []).filter((line) => line.episodeId === episodeId);
  const tracks = ["dialogue", "sfx", "ambience", "bgm"];
  const run = (operation, message) => operation().then(() => actions.notify?.(message)).catch((error) => actions.notify?.(error?.message || "时间线操作失败", "error"));
  return <div className="module-page"><PageHeader eyebrow="Timeline" title={`${episodeId} 可编辑时间线`} description="视频镜头和音频片段都可以调整起点、时长与轨道状态；保存会写回后台数据库。" action={<div className="page-header-actions"><select value={episodeId || ""} onChange={(event) => setEpisodeId(event.target.value)}>{project.episodes.map((episode) => <option key={episode.id} value={episode.id}>{episode.id} · {episode.title}</option>)}</select><button type="button" onClick={() => actions.mixdownEpisode(episodeId)}><SpeakerHigh size={17} />生成混音</button><button className="primary-action" type="button" onClick={() => actions.renderEpisode(episodeId)}>渲染 MP4</button></div>} />
    <section className="module-section timeline-editor"><div className="timeline-ruler">{Array.from({ length: Math.ceil(total / 4) + 1 }, (_, index) => <span key={index}>{index * 4}s</span>)}</div><div className="timeline-track"><strong>Video</strong><div>{videoClips.map((clip) => <div className="timeline-video-item" key={clip.id} style={{ flex: Math.max(1, (clip.durationMs || 1000) / 1000) }}><button type="button"><img src={clip.image || "/assets/shot-wide.png"} alt="" /><span>{clip.shotId}</span><small>{Math.round((clip.durationMs || 0) / 1000)}s</small></button><TimelineVideoClipEditor clip={clip} onSave={(id, patch) => run(() => actions.patchVideoClip(id, patch), "视频片段已保存")} onDelete={(id) => run(() => actions.deleteVideoClip(id), "视频片段已移除")} /></div>)}{!videoClips.length && <span className="timeline-empty-track">本集还没有视频片段</span>}</div></div>{omittedShots.length > 0 && <div className="timeline-add-clips"><span>未入轨镜头</span>{omittedShots.map((shot) => <button type="button" key={shot.id} onClick={() => run(() => actions.createVideoClip({ shotId: shot.id }), `${shot.id} 已恢复到视频轨道`)}>{shot.id} · 恢复</button>)}</div>}{tracks.map((track) => { const clips = audioClips.filter((clip) => clip.trackType === track); return <div className="timeline-track slim" key={track}><strong>{track === "dialogue" ? "Dialogue" : track.toUpperCase()}</strong><div>{clips.map((clip) => <div key={clip.id} style={{ flex: Math.max(1, (clip.durationMs || 1000) / 1000) }}><span>{clip.linkedDialogueLineId || `${track} clip`} · {Math.round((clip.durationMs || 0) / 1000)}s</span><TimelineClipEditor clip={clip} onSave={(id, patch) => run(() => actions.patchAudioClip(id, patch), "音频片段已保存")} onDelete={(id) => run(() => actions.deleteAudioClip(id), "音频片段已删除")} /></div>)}{!clips.length && <span className="timeline-empty-track">{track === "dialogue" ? `${audioLines.filter((line) => line.activeTake).length} 条可用对白，去声音工作台入轨` : "空轨道"}</span>}</div></div>; })}</section>
  </div>;
}

function QCPage({ project, actions, onReviewShot, onRegenerate }) {
  const shots = project.shots.filter((shot) => shot.episodeId === project.currentEpisodeId);
  const [runNotice, setRunNotice] = useState("");
  const run = async (operation, kind) => {
    try {
      const result = await operation();
      if (kind === "visual") {
        const semanticChecks = (result.visual || []).flatMap((item) => item.checks || []).filter((item) => item.type === "vision_semantic");
        setRunNotice(semanticChecks.length ? `视觉 QC 已完成：本次有 ${semanticChecks.length} 条 LLM 语义结论写入 QC 记录。` : "视觉 QC 已完成：当前使用本地像素和规则检查；配置 LLM 后会追加语义检查。");
      } else {
        setRunNotice(`连续性检查已完成：${result.findings?.filter((item) => item.status !== "pass").length || 0} 个镜头需要复核。`);
      }
    } catch (error) {
      setRunNotice(error?.message || "检查失败，请确认 FastAPI 和 Provider 配置");
    }
  };
  return <div className="module-page"><PageHeader eyebrow="AI QC" title="质量检查" description="检查角色一致性、画面连续性和镜头生产状态；配置 LLM 后会追加图像语义审核。" action={<div className="page-header-actions"><button type="button" onClick={() => run(actions.runProjectQC, "visual")}>运行视觉 QC</button><button className="primary-action" type="button" onClick={() => run(actions.runContinuityCheck, "continuity")}>检查连续性</button></div>} />
    {runNotice && <div className="qc-run-notice">{runNotice}</div>}
    <div className="qc-summary"><div><strong>{shots.filter((shot) => shot.qcScore >= 90).length}</strong><span>通过</span></div><div><strong>{shots.filter((shot) => shot.qcScore && shot.qcScore < 90).length}</strong><span>需复核</span></div><div><strong>{shots.filter((shot) => !shot.qcScore).length}</strong><span>未检测</span></div></div>
    <section className="module-section qc-list">{shots.map((shot) => <article key={shot.id}><img src={shot.image} alt="" /><div><span>{shot.id}</span><strong>{shot.description}</strong><small>{shot.qcScore ? `角色一致性 ${shot.qcScore}%` : "等待生成后检测"}</small></div><em className={shot.qcScore >= 90 ? "pass" : shot.qcScore ? "warning" : "pending"}>{shot.qcScore ? `${shot.qcScore}%` : "--"}</em><div>{shot.status === "已生成" && <button type="button" onClick={() => onReviewShot(shot.id)}>{shot.reviewed ? <CheckCircle size={16} weight="fill" /> : <Check size={16} />}{shot.reviewed ? "已审核" : "通过"}</button>}{shot.qcScore && shot.qcScore < 90 && <button type="button" onClick={() => onRegenerate(shot.id)}>重新生成</button>}</div></article>)}</section>
  </div>;
}

function ExportPage({ project, onExport }) {
  return <div className="module-page"><PageHeader eyebrow="Export" title="项目导出" description="打包项目数据、镜头清单和生产元数据。" />
    <div className="export-layout"><section className="module-section export-card"><span className="export-icon"><DownloadSimple size={26} /></span><h2>Project Package</h2><p>包含项目 JSON、Story Bible、剧集、资产、镜头、版本、成本与 QC 记录。</p><ul><li>project.json</li><li>story-bible.json</li><li>shots.json</li><li>tasks-and-costs.json</li></ul><button className="primary-action" type="button" onClick={onExport}><DownloadSimple size={18} />下载项目包</button></section><section className="module-section export-summary"><h2>导出检查</h2><div><span>剧集规划</span><strong>{project.episodes.length} 集</strong></div><div><span>镜头数据</span><strong>{project.shots.length} 个</strong></div><div><span>资产</span><strong>{Object.values(project.assets).flat().length} 个</strong></div><div><span>生成任务</span><strong>{project.tasks.length} 条</strong></div><div><span>总成本</span><strong>¥{project.spent.toFixed(2)}</strong></div></section></div>
  </div>;
}

const LOCAL_LLM_PRESETS = [
  { id: "minimax-m2.1", label: "MiniMax M2.1 · 本地 vLLM", name: "MiniMax Local · vLLM", url: "http://127.0.0.1:8001/v1", model: "MiniMaxAI/MiniMax-M2.1", note: "适合 Agent 和剧本结构化输出" },
  { id: "minimax-m2.7", label: "MiniMax M2.7 · 本地 vLLM", name: "MiniMax Local · vLLM", url: "http://127.0.0.1:8001/v1", model: "MiniMaxAI/MiniMax-M2.7", note: "适合 Agent 和长上下文任务" },
  { id: "minimax-vl", label: "MiniMax VL · 本地视觉模型", name: "MiniMax VL · vLLM", url: "http://127.0.0.1:8001/v1", model: "MiniMaxAI/MiniMax-VL-01", note: "用于视觉 QC；需本地服务支持图像输入" },
];

function ModelDiscoveryResult({ catalog }) {
  if (!catalog) return null;
  return <div className="model-discovery-result"><div className="model-discovery-summary"><strong>已发现 {catalog.count} 个模型</strong><span>{catalog.endpoint}</span></div><div className="model-discovery-groups">{(catalog.groups || []).map((group) => <div className="model-discovery-group" key={group.type}><div><b>{group.label}</b><small>{group.count}</small></div><p>{group.models.map((model) => <span key={model.modelId} title={model.modelId}>{model.displayName}</span>)}</p></div>)}</div></div>;
}

function SettingsPage({ project, onUpdateProject, backendStatus, providerInfo, actions }) {
  const [settings, setSettings] = useState({ providerUrl: "", providerName: "External Video API", providerModel: "video-default", providerApiKey: "", providerApiKeyMasked: "", apiKeySet: false, voiceProvider: "mock", voiceModel: "voice-default", cosyvoiceUrl: "", chatterboxUrl: "", gptSovitsUrl: "", llmProviderUrl: "", llmProviderName: "OpenAI Compatible", llmModel: "gpt-4o-mini", llmApiKey: "", llmApiKeyMasked: "", llmApiKeySet: false, secretStorage: null });
  const [settingsBusy, setSettingsBusy] = useState(false);
  const [settingsNotice, setSettingsNotice] = useState("");
  const [modelCatalogs, setModelCatalogs] = useState({ media: null, llm: null });
  const [discovering, setDiscovering] = useState("");
  const providerLabel = providerInfo?.mode === "remote" ? `外部接口 · ${providerInfo.provider}` : providerInfo?.mode === "demo" ? "本地演示生成器" : "未连接";
  useEffect(() => {
    if (backendStatus !== "online") return;
    actions.getProviderSettings().then(setSettings).catch(() => setSettingsNotice("API 配置读取失败"));
  }, [backendStatus]);

  const update = (key, value) => setSettings((current) => ({ ...current, [key]: value, ...(key === "llmProviderUrl" || key === "llmProviderName" || key === "llmModel" ? { llmPreset: "custom" } : {}) }));
  const applyLLMPreset = (presetId) => {
    const preset = LOCAL_LLM_PRESETS.find((item) => item.id === presetId);
    if (!preset) {
      update("llmPreset", "custom");
      return;
    }
    setSettings((current) => ({ ...current, llmPreset: preset.id, llmProviderUrl: preset.url, llmProviderName: preset.name, llmModel: preset.model }));
    setSettingsNotice(`${preset.label} 已填入。${preset.note}；请确认本地服务端口后保存。`);
  };
  const discoveryPayload = (kind, values = settings) => kind === "llm"
    ? { kind: "llm", url: values.llmProviderUrl, apiKey: values.llmApiKey, providerName: values.llmProviderName }
    : { kind: "video", url: values.providerUrl, apiKey: values.providerApiKey, providerName: values.providerName };
  const discoverModels = async (kind, values = settings) => {
    const payload = discoveryPayload(kind, values);
    if (!payload.url) {
      setSettingsNotice("请先填写 API 地址");
      return null;
    }
    setDiscovering(kind);
    try {
      const result = await actions.discoverModels(payload);
      setModelCatalogs((current) => ({ ...current, [kind === "llm" ? "llm" : "media"]: result }));
      const recommended = result.recommended || {};
      setSettings((current) => ({ ...current, ...(kind === "llm" && !current.llmModel ? { llmModel: recommended.text || recommended.vision || "" } : {}), ...(kind !== "llm" && !current.providerModel ? { providerModel: recommended.image || recommended.video || "" } : {}) }));
      setSettingsNotice(`已读取 ${result.count} 个模型，并自动分为 ${result.groups.map((group) => group.label).join("、")}。`);
      return result;
    } catch (error) {
      setSettingsNotice(error?.message || "模型列表读取失败；请确认接口支持 /models");
      return null;
    } finally {
      setDiscovering("");
    }
  };
  const saveSettings = async () => {
    setSettingsBusy(true);
    setSettingsNotice("");
    try {
      const next = await actions.saveProviderSettings(settings);
      setSettings({ ...next, llmPreset: settings.llmPreset });
      window.dispatchEvent(new Event("short-drama-settings-saved"));
      setSettingsNotice("API 配置已保存，正在读取模型列表…");
      const discoveries = await Promise.all([
        next.providerUrl ? discoverModels("media", { ...settings, ...next }) : null,
        next.llmProviderUrl ? discoverModels("llm", { ...settings, ...next }) : null,
      ]);
      if (!discoveries.some(Boolean)) setSettingsNotice("API 配置已保存；接口未返回标准模型列表，可继续手动填写模型名。");
    } catch (error) {
      setSettingsNotice(error?.message || "API 配置保存失败");
    } finally {
      setSettingsBusy(false);
    }
  };
  const testSettings = async (kind) => {
    setSettingsBusy(true);
    setSettingsNotice("");
    try {
      const result = await actions.testProviderSettings({ ...settings, kind });
      setSettingsNotice(result.message || (result.ok ? "接口连接成功" : "接口连接失败"));
    } catch (error) {
      setSettingsNotice(error?.message || "接口测试失败");
    } finally {
      setSettingsBusy(false);
    }
  };
  return <div className="module-page settings-page"><PageHeader eyebrow="Settings" title="项目设置" description="项目资料和生成 API 都在这里配置，保存后后台任务会立即切换。" /><section className="module-section settings-form"><label>项目名称<input value={project.title} onChange={(event) => onUpdateProject({ title: event.target.value })} /></label><label>项目状态<select value={project.status} onChange={(event) => onUpdateProject({ status: event.target.value })}>{["策划中", "制作中", "审核中", "已完成"].map((item) => <option key={item}>{item}</option>)}</select></label><label>预算（元）<input type="number" min="0" value={project.budget} onChange={(event) => onUpdateProject({ budget: Number(event.target.value) })} /></label><label>计划完成日期<input type="date" value={project.dueDate} onChange={(event) => onUpdateProject({ dueDate: event.target.value })} /></label></section><section className="module-section settings-api-card"><div className="settings-api-heading"><div><span className="section-kicker">Provider Settings</span><h2>统一生成 API 配置</h2><p>图片、视频、声音和 LLM 都从这里配置。API Key 仅保存在本机后台，页面只显示掩码。</p></div><span className={`status-pill ${backendStatus === "online" ? "success" : "muted"}`}>{providerLabel}</span></div><div className="settings-api-form"><label className="settings-api-wide">通用图片/视频 API 地址<span>POST JSON 接口，例如你的统一生成网关</span><input value={settings.providerUrl || ""} onChange={(event) => update("providerUrl", event.target.value)} placeholder="https://your-provider.example.com/v1/generate" /></label><label>Provider 名称<input value={settings.providerName || ""} onChange={(event) => update("providerName", event.target.value)} placeholder="External Video API" /></label><label>默认模型<input value={settings.providerModel || ""} onChange={(event) => update("providerModel", event.target.value)} placeholder="video-default" /></label><label className="settings-api-wide">API Key<input type="password" value={settings.providerApiKey || ""} onChange={(event) => update("providerApiKey", event.target.value)} placeholder={settings.apiKeySet ? "已保存密钥，留空保持不变" : "sk-..."} autoComplete="off" /></label><div className="settings-api-wide settings-api-actions"><button type="button" onClick={() => testSettings("video")} disabled={settingsBusy || !settings.providerUrl}>测试通用接口</button></div><label className="settings-api-wide">MiniMax / LLM 快速预设<select value={settings.llmPreset || "custom"} onChange={(event) => applyLLMPreset(event.target.value)}><option value="custom">自定义 OpenAI-compatible</option>{LOCAL_LLM_PRESETS.map((preset) => <option value={preset.id} key={preset.id}>{preset.label}</option>)}</select><span>本地 vLLM 默认使用 8001，避免和 Short Drama OS 的 FastAPI 8000 端口冲突。</span></label><label className="settings-api-wide">LLM / Agent API 地址<span>填写 vLLM 的基础地址，适配器会自动请求 /chat/completions</span><input value={settings.llmProviderUrl || ""} onChange={(event) => update("llmProviderUrl", event.target.value)} placeholder="http://127.0.0.1:8001/v1" /></label><label>LLM Provider 名称<input value={settings.llmProviderName || ""} onChange={(event) => update("llmProviderName", event.target.value)} placeholder="MiniMax Local · vLLM" /></label><label>LLM 模型<input value={settings.llmModel || ""} onChange={(event) => update("llmModel", event.target.value)} placeholder="MiniMaxAI/MiniMax-M2.1" /></label><label className="settings-api-wide">LLM API Key<input type="password" value={settings.llmApiKey || ""} onChange={(event) => update("llmApiKey", event.target.value)} placeholder={settings.llmApiKeySet ? "已保存密钥，留空保持不变" : "本地通常留空"} autoComplete="off" /></label><div className="settings-api-wide settings-api-actions"><button type="button" onClick={() => testSettings("llm")} disabled={settingsBusy || !settings.llmProviderUrl}>测试 MiniMax / LLM</button></div><label>声音 Provider<select value={settings.voiceProvider || "mock"} onChange={(event) => update("voiceProvider", event.target.value)}>{[["mock", "本地 WAV Demo"], ["cosyvoice", "CosyVoice HTTP"], ["chatterbox", "Chatterbox HTTP"], ["gpt-sovits", "GPT-SoVITS HTTP"]].map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label><label>声音模型<input value={settings.voiceModel || ""} onChange={(event) => update("voiceModel", event.target.value)} placeholder="voice-default" /></label><label>CosyVoice 地址<input value={settings.cosyvoiceUrl || ""} onChange={(event) => update("cosyvoiceUrl", event.target.value)} placeholder="http://127.0.0.1:50000/..." /></label><label>Chatterbox 地址<input value={settings.chatterboxUrl || ""} onChange={(event) => update("chatterboxUrl", event.target.value)} placeholder="http://127.0.0.1:8001/tts" /></label><label>GPT-SoVITS 地址<input value={settings.gptSovitsUrl || ""} onChange={(event) => update("gptSovitsUrl", event.target.value)} placeholder="http://127.0.0.1:9880/tts" /></label><div className="settings-api-actions settings-api-wide"><button type="button" onClick={() => testSettings("audio")} disabled={settingsBusy || settings.voiceProvider === "mock"}>测试声音接口</button><button className="primary-action" type="button" onClick={saveSettings} disabled={settingsBusy || backendStatus !== "online"}>{settingsBusy ? "保存中…" : "保存 API 配置"}</button></div></div>{settingsNotice && <div className="settings-api-notice">{settingsNotice}</div>}<small className="settings-api-footnote">连接测试会访问 LLM 的 /models 路径；MiniMax M2 系列适合 Agent，MiniMax VL 系列才适合视觉输入。未配置视觉模型时，系统仍会执行本地像素和连续性检查。</small></section><section className="module-section api-status-card"><div><span className="section-kicker">API Runtime</span><h3>任务运行状态</h3><p>{backendStatus === "online" ? (providerInfo?.mode === "remote" ? "已配置外部生成平台，新的任务会写入持久队列并由后台执行。" : "当前使用本地演示 Provider；保存外部地址后会自动切换。") : "FastAPI 未连接，生成任务无法同步到服务端。"}</p></div><span className={`status-pill ${backendStatus === "online" ? "success" : "muted"}`}>{providerLabel}</span></section></div>;
}

function ModelDiscoveryPanel({ actions, backendStatus }) {
  const [settings, setSettings] = useState(null);
  const [catalogs, setCatalogs] = useState({ media: null, llm: null });
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState("");
  useEffect(() => {
    if (backendStatus !== "online") return;
    actions.getProviderSettings().then((next) => {
      setSettings(next);
      const requests = [];
      if (next.providerUrl) requests.push(actions.discoverModels({ kind: "video", url: next.providerUrl, apiKey: next.providerApiKey, providerName: next.providerName }).then((result) => setCatalogs((current) => ({ ...current, media: result }))));
      if (next.llmProviderUrl) requests.push(actions.discoverModels({ kind: "llm", url: next.llmProviderUrl, apiKey: next.llmApiKey, providerName: next.llmProviderName }).then((result) => setCatalogs((current) => ({ ...current, llm: result }))));
      return Promise.allSettled(requests);
    }).catch(() => setNotice("模型目录读取失败，请检查 API 地址和 /models 接口。"));
  }, [backendStatus]);
  useEffect(() => {
    const handleSaved = () => {
      actions.getProviderSettings().then((next) => {
        setSettings(next);
        const requests = [];
        if (next.providerUrl) requests.push(actions.discoverModels({ kind: "video", url: next.providerUrl, apiKey: next.providerApiKey, providerName: next.providerName }).then((result) => setCatalogs((current) => ({ ...current, media: result }))));
        if (next.llmProviderUrl) requests.push(actions.discoverModels({ kind: "llm", url: next.llmProviderUrl, apiKey: next.llmApiKey, providerName: next.llmProviderName }).then((result) => setCatalogs((current) => ({ ...current, llm: result }))));
        return Promise.allSettled(requests);
      }).catch(() => setNotice("模型目录读取失败，请检查 API 地址和 /models 接口。"));
    };
    window.addEventListener("short-drama-settings-saved", handleSaved);
    return () => window.removeEventListener("short-drama-settings-saved", handleSaved);
  }, [backendStatus]);
  const refresh = async (kind) => {
    if (!settings) return;
    const payload = kind === "llm" ? { kind, url: settings.llmProviderUrl, apiKey: settings.llmApiKey, providerName: settings.llmProviderName } : { kind: "video", url: settings.providerUrl, apiKey: settings.providerApiKey, providerName: settings.providerName };
    if (!payload.url) { setNotice("请先在上方填写并保存 API 地址。"); return; }
    setBusy(kind);
    try {
      const result = await actions.discoverModels(payload);
      setCatalogs((current) => ({ ...current, [kind === "llm" ? "llm" : "media"]: result }));
      setNotice(`${result.provider} 已发现 ${result.count} 个模型，并完成自动分类。`);
    } catch (error) {
      setNotice(error?.message || "模型目录读取失败");
    } finally {
      setBusy("");
    }
  };
  return <section className="module-section model-discovery-card"><div className="model-discovery-heading"><div><span className="section-kicker">MODEL DISCOVERY</span><h2>自动模型目录</h2><p>保存 API 后自动读取 /models，并按文本、视觉、图片、视频、音频和向量模型分类。</p></div><span className="status-pill success">已接入</span></div><div className="model-discovery-columns"><div><div className="model-discovery-toolbar"><strong>图片 / 视频 Provider</strong><button type="button" onClick={() => refresh("media")} disabled={busy === "media"}>{busy === "media" ? "读取中…" : "刷新模型"}</button></div><ModelDiscoveryResult catalog={catalogs.media} /></div><div><div className="model-discovery-toolbar"><strong>LLM / Agent Provider</strong><button type="button" onClick={() => refresh("llm")} disabled={busy === "llm"}>{busy === "llm" ? "读取中…" : "刷新模型"}</button></div><ModelDiscoveryResult catalog={catalogs.llm} /></div></div>{notice && <div className="settings-api-notice">{notice}</div>}</section>;
}

function ProviderAsyncSettings({ actions, backendStatus }) {
  const [statusUrl, setStatusUrl] = useState("");
  const [notice, setNotice] = useState("");
  useEffect(() => {
    if (backendStatus !== "online") return;
    actions.getProviderSettings().then((settings) => setStatusUrl(settings.providerStatusUrl || "")).catch(() => {});
  }, [backendStatus]);
  const save = async () => {
    try {
      await actions.saveProviderSettings({ providerStatusUrl: statusUrl });
      setNotice("异步状态地址已保存");
    } catch (error) {
      setNotice(error?.message || "保存失败");
    }
  };
  return <section className="module-section provider-async-card"><div><span className="section-kicker">ASYNC TASK ADAPTER</span><h2>异步任务状态地址（可选）</h2><p>如果生成接口只返回 task_id，没有返回 status_url，请填写任务查询地址模板。</p></div><div className="provider-async-form"><input value={statusUrl} onChange={(event) => setStatusUrl(event.target.value)} placeholder="https://api.example.com/tasks/{task_id}" /><button type="button" onClick={save} disabled={backendStatus !== "online"}>保存</button></div>{notice && <small>{notice}</small>}</section>;
}

export function ModulePage({ activeNav, project, stats, actions }) {
  if (activeNav === "Agent") return <AgentPage project={project} stats={stats} actions={actions} />;
  if (activeNav === "概览") return <OverviewPage project={project} stats={stats} onNavigate={actions.navigate} />;
  if (activeNav === "故事") return <ScriptPage project={project} actions={actions} />;
  if (activeNav === "剧集") return <EpisodesPage project={project} onOpenEpisode={actions.openEpisode} />;
  if (activeNav === "素材库") return <AssetsPage project={project} onAddAsset={actions.addAsset} onUpdateAsset={actions.updateAsset} actions={actions} />;
  if (activeNav === "生图") return <AssetGenerationPage project={project} actions={actions} />;
  if (activeNav === "生成") return <GenerationPage project={project} onRetry={actions.retryTask} onCancel={actions.cancelTask} onNavigate={actions.navigate} />;
  if (activeNav === "声音") return <AudioPage project={project} actions={actions} />;
  if (activeNav === "时间线") return <TimelinePage project={project} actions={actions} />;
  if (activeNav === "质检") return <QCPage project={project} actions={actions} onReviewShot={actions.reviewShot} onRegenerate={actions.regenerateShot} />;
  if (activeNav === "导出") return <ExportPage project={project} onExport={actions.exportProject} />;
  return <ModelSettingsPage project={project} onUpdateProject={actions.updateProject} backendStatus={actions.backendStatus} providerInfo={actions.providerInfo} actions={actions} />;
}

export function SearchDialog({ open, project, onClose, onOpenResult }) {
  const [query, setQuery] = useState("");
  const results = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return [];
    const episodes = project.episodes.filter((item) => `${item.id}${item.title}${item.hook}`.toLowerCase().includes(normalized)).slice(0, 4).map((item) => ({ type: "剧集", id: item.id, title: item.title, target: "剧集" }));
    const shots = project.shots.filter((item) => `${item.id}${item.description}${item.dialogue}`.toLowerCase().includes(normalized)).slice(0, 5).map((item) => ({ type: "镜头", id: item.id, title: item.description, target: "分镜" }));
    const assets = Object.values(project.assets).flat().filter((item) => `${item.id}${item.name}${item.description}`.toLowerCase().includes(normalized)).slice(0, 4).map((item) => ({ type: "资产", id: item.id, title: item.name, target: "素材库" }));
    return [...episodes, ...shots, ...assets];
  }, [project, query]);
  if (!open) return null;
  return <div className="dialog-backdrop" onMouseDown={onClose}><section className="search-dialog" onMouseDown={(event) => event.stopPropagation()}><div className="search-input"><MagnifyingGlass size={20} /><input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索剧集、镜头、角色、场景…" /><button type="button" onClick={onClose}><X size={18} /></button></div><div className="search-results">{query && !results.length ? <div className="search-empty"><Warning size={20} /><span>没有找到匹配内容</span></div> : results.map((result) => <button type="button" key={`${result.type}-${result.id}`} onClick={() => onOpenResult(result)}><span>{result.type}</span><strong>{result.id}</strong><em>{result.title}</em><ArrowRight size={16} /></button>)}</div></section></div>;
}
