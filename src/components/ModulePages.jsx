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
  Stop,
  Trash,
  Warning,
  X,
} from "@phosphor-icons/react";

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

  useEffect(() => {
    if (project.currentEpisodeId && project.currentEpisodeId !== episodeId && !running) {
      setEpisodeId(project.currentEpisodeId);
    }
  }, [project.currentEpisodeId, running]);

  const episode = project.episodes.find((item) => item.id === episodeId) || project.episodes[0];
  const currentShots = project.shots.filter((shot) => shot.episodeId === episodeId);
  const addLog = (message) => setLogs((current) => [...current.slice(-7), message]);
  const updateStep = (id, status) => setStepState((current) => current.map((step) => step.id === id ? { ...step, status } : step));

  const runAgent = async () => {
    if (running || actions.backendStatus !== "online") return;
    setRunning(true);
    setResult("");
    setStepState(agentPlan.map(([id]) => ({ id, status: "pending" })));
    setLogs([`收到目标：${goal.trim() || `推进 ${episodeId} 的剧本生产`}`]);
    let activeStep = "context";
    try {
      updateStep(activeStep, "running");
      addLog(`读取 ${episodeId} 的故事规则与当前生产状态`);
      await Promise.resolve();
      updateStep(activeStep, "done");

      activeStep = "matrix";
      updateStep(activeStep, "running");
      addLog("正在整理本集矩阵，确保先有节奏再进入镜头");
      await actions.generateMatrix(episodeId, {});
      updateStep(activeStep, "done");

      activeStep = "scene";
      updateStep(activeStep, "running");
      let scenes = await actions.loadScenes(episodeId);
      let scene = scenes[0];
      if (!scene) {
        addLog("当前剧集没有场景，Agent 自动创建第一个可拍场景");
        scene = await actions.createScene(episodeId, { title: "Agent 场景", purpose: "推进本集核心冲突并留下下一集问题", summary: goal.trim(), timeOfDay: "夜晚" });
      } else {
        addLog(`复用场景 ${scene.id}：${scene.title}`);
      }
      updateStep(activeStep, "done");

      activeStep = "script";
      updateStep(activeStep, "running");
      addLog(`正在为 ${scene.id} 生成动作与对白节拍`);
      await actions.generateSceneScript(scene.id, {});
      updateStep(activeStep, "done");

      activeStep = "breakdown";
      updateStep(activeStep, "running");
      addLog("正在把场景节拍拆成可生成镜头");
      const breakdown = await actions.generateBreakdown(scene.id, {});
      updateStep(activeStep, "done");
      setResult(`已完成 ${episodeId}：${scene.id} 已准备 ${breakdown.length} 个镜头，下一步可进入分镜工作台执行生成。`);
      addLog("Agent 已完成本轮任务，等待你的审核");
    } catch (error) {
      updateStep(activeStep, "failed");
      addLog(`执行暂停：${error?.message || "接口返回异常"}`);
      setResult("本轮执行已暂停，请处理错误后重新运行。");
    } finally {
      setRunning(false);
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
        <div className="agent-command-footer"><span>{actions.backendStatus === "online" ? "Agent 会在写入前继承故事圣经和不可违反规则。" : "FastAPI 未连接，暂时不能执行 Agent 任务。"}</span><button className="primary-action" type="button" onClick={runAgent} disabled={running || actions.backendStatus !== "online"}>{running ? <><Stop size={16} />停止中…</> : <><Play size={16} weight="fill" />开始执行</>}</button></div>
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

  const goNext = () => {
    const next = scriptSteps[currentStep + 1];
    if (next) setStep(next[0]);
  };

  return <div className="module-page script-page">
    <PageHeader eyebrow="Script Pipeline" title="剧本工作台" description="把故事规则逐步落成剧集矩阵、场景剧本和可生成的分镜。每一步都能保存，随时继续。" action={<div className="script-header-meta"><span>{episode?.id} {episode?.title}</span><strong>{currentStep + 1} / {scriptSteps.length}</strong></div>} />
    <nav className="script-stepper" aria-label="剧本生产流程">{scriptSteps.map(([id, label, hint], index) => <button className={step === id ? "is-active" : index < currentStep ? "is-done" : ""} key={id} type="button" onClick={() => setStep(id)}><i>{index < currentStep ? <Check size={13} weight="bold" /> : index + 1}</i><span><strong>{label}</strong><small>{hint}</small></span>{index < scriptSteps.length - 1 && <ArrowRight size={15} />}</button>)}</nav>
    <div className="script-toolbar"><label>当前剧集<select value={episodeId} onChange={(event) => { setEpisodeId(event.target.value); actions.updateProject({ currentEpisodeId: event.target.value }); }}><option value="">选择剧集</option>{project.episodes.map((item) => <option key={item.id} value={item.id}>{item.id}　{item.title}</option>)}</select></label><span className="script-save-state">{busy ? "处理中…" : notice || "所有修改都保存到项目数据库"}</span><button type="button" onClick={() => actions.openEpisode(episodeId)}>进入分镜 <ArrowRight size={15} /></button></div>
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

function AssetsPage({ project, onAddAsset, onUpdateAsset }) {
  const [tab, setTab] = useState("characters");
  const config = { characters: ["角色", "新增角色"], locations: ["场景", "新增场景"], props: ["道具", "新增道具"] };
  const items = project.assets[tab];
  return <div className="module-page"><PageHeader eyebrow="Asset System" title="项目资产库" description="角色、场景和道具在所有镜头中保持统一引用。" action={<button className="primary-action" type="button" onClick={() => onAddAsset(tab)}><Plus size={18} />{config[tab][1]}</button>} />
    <div className="page-tabs">{Object.entries(config).map(([key, [label]]) => <button className={tab === key ? "is-active" : ""} key={key} onClick={() => setTab(key)} type="button">{label}<span>{project.assets[key].length}</span></button>)}</div>
    <div className="asset-grid">{items.map((item) => <article className="asset-card" key={item.id}><img src={item.image} alt="" /><div><span>{item.id}</span><input value={item.name} onChange={(event) => onUpdateAsset(tab, item.id, { name: event.target.value })} /><small>{item.meta}</small><textarea value={item.description} onChange={(event) => onUpdateAsset(tab, item.id, { description: event.target.value })} /><em>{item.status}</em></div></article>)}</div>
  </div>;
}

function GenerationPage({ project, onRetry, onCancel, onNavigate }) {
  return <div className="module-page"><PageHeader eyebrow="Generation Center" title="生成任务" description="统一查看模型任务、成本和失败重试。" action={<button className="primary-action" type="button" onClick={() => onNavigate("分镜")}><Sparkle size={18} />选择镜头生成</button>} />
    <div className="task-summary"><div><span>运行中</span><strong>{project.tasks.filter((task) => task.status === "Running").length}</strong></div><div><span>已成功</span><strong>{project.tasks.filter((task) => task.status === "Success").length}</strong></div><div><span>失败</span><strong>{project.tasks.filter((task) => task.status === "Failed").length}</strong></div><div><span>任务成本</span><strong>¥{project.tasks.reduce((sum, task) => sum + task.cost, 0).toFixed(2)}</strong></div></div>
    <section className="module-section task-table"><div className="task-table-head"><span>任务</span><span>镜头</span><span>类型</span><span>模型</span><span>状态</span><span>成本</span><span>操作</span></div>{project.tasks.map((task) => <div key={task.id}><code>{task.id}</code><strong>{task.shotId}</strong><span>{task.type}</span><span>{task.model}</span><em className={`task-status ${task.status}`}>{task.status}</em><span>¥{task.cost.toFixed(2)}</span><span className="table-actions">{task.status === "Failed" || task.status === "Cancelled" ? <button type="button" onClick={() => onRetry(task.id)}>重试</button> : null}{task.status === "Running" ? <button type="button" onClick={() => onCancel(task.id)}>取消</button> : null}</span></div>)}</section>
  </div>;
}

function TimelinePage({ project }) {
  const shots = project.shots.filter((shot) => shot.episodeId === project.currentEpisodeId);
  const total = shots.reduce((sum, shot) => sum + shot.duration, 0) || 1;
  return <div className="module-page"><PageHeader eyebrow="Timeline" title={`${project.currentEpisodeId} 轻量时间线`} description="调整镜头顺序、对白和时长；复杂剪辑可在导出后继续完成。" />
    <section className="module-section timeline-editor"><div className="timeline-ruler">{Array.from({ length: Math.ceil(total / 4) + 1 }, (_, index) => <span key={index}>{index * 4}s</span>)}</div><div className="timeline-track"><strong>Video</strong><div>{shots.map((shot) => <button key={shot.id} style={{ flex: Math.max(1, shot.duration) }} type="button"><img src={shot.image} alt="" /><span>{shot.id}</span><small>{shot.duration}s</small></button>)}</div></div><div className="timeline-track slim"><strong>Voice</strong><div>{shots.map((shot) => <span key={shot.id} style={{ flex: Math.max(1, shot.duration) }}>{shot.dialogue.slice(0, 8)}</span>)}</div></div><div className="timeline-track slim"><strong>Subtitle</strong><div>{shots.map((shot) => <span key={shot.id} style={{ flex: Math.max(1, shot.duration) }}>{shot.id}</span>)}</div></div></section>
  </div>;
}

function QCPage({ project, onReviewShot, onRegenerate }) {
  const shots = project.shots.filter((shot) => shot.episodeId === project.currentEpisodeId);
  return <div className="module-page"><PageHeader eyebrow="AI QC" title="质量检查" description="检查角色一致性、画面连续性和镜头生产状态。" />
    <div className="qc-summary"><div><strong>{shots.filter((shot) => shot.qcScore >= 90).length}</strong><span>通过</span></div><div><strong>{shots.filter((shot) => shot.qcScore && shot.qcScore < 90).length}</strong><span>需复核</span></div><div><strong>{shots.filter((shot) => !shot.qcScore).length}</strong><span>未检测</span></div></div>
    <section className="module-section qc-list">{shots.map((shot) => <article key={shot.id}><img src={shot.image} alt="" /><div><span>{shot.id}</span><strong>{shot.description}</strong><small>{shot.qcScore ? `角色一致性 ${shot.qcScore}%` : "等待生成后检测"}</small></div><em className={shot.qcScore >= 90 ? "pass" : shot.qcScore ? "warning" : "pending"}>{shot.qcScore ? `${shot.qcScore}%` : "--"}</em><div>{shot.status === "已生成" && <button type="button" onClick={() => onReviewShot(shot.id)}>{shot.reviewed ? <CheckCircle size={16} weight="fill" /> : <Check size={16} />}{shot.reviewed ? "已审核" : "通过"}</button>}{shot.qcScore && shot.qcScore < 90 && <button type="button" onClick={() => onRegenerate(shot.id)}>重新生成</button>}</div></article>)}</section>
  </div>;
}

function ExportPage({ project, onExport }) {
  return <div className="module-page"><PageHeader eyebrow="Export" title="项目导出" description="打包项目数据、镜头清单和生产元数据。" />
    <div className="export-layout"><section className="module-section export-card"><span className="export-icon"><DownloadSimple size={26} /></span><h2>Project Package</h2><p>包含项目 JSON、Story Bible、剧集、资产、镜头、版本、成本与 QC 记录。</p><ul><li>project.json</li><li>story-bible.json</li><li>shots.json</li><li>tasks-and-costs.json</li></ul><button className="primary-action" type="button" onClick={onExport}><DownloadSimple size={18} />下载项目包</button></section><section className="module-section export-summary"><h2>导出检查</h2><div><span>剧集规划</span><strong>{project.episodes.length} 集</strong></div><div><span>镜头数据</span><strong>{project.shots.length} 个</strong></div><div><span>资产</span><strong>{Object.values(project.assets).flat().length} 个</strong></div><div><span>生成任务</span><strong>{project.tasks.length} 条</strong></div><div><span>总成本</span><strong>¥{project.spent.toFixed(2)}</strong></div></section></div>
  </div>;
}

function SettingsPage({ project, onUpdateProject, backendStatus, providerInfo }) {
  const providerLabel = providerInfo?.mode === "remote" ? `外部接口 · ${providerInfo.provider}` : providerInfo?.mode === "demo" ? "本地演示生成器" : "未连接";
  return <div className="module-page"><PageHeader eyebrow="Settings" title="项目设置" description="调整项目名称、预算和计划完成日期。" /><section className="module-section settings-form"><label>项目名称<input value={project.title} onChange={(event) => onUpdateProject({ title: event.target.value })} /></label><label>项目状态<select value={project.status} onChange={(event) => onUpdateProject({ status: event.target.value })}>{["策划中", "制作中", "审核中", "已完成"].map((item) => <option key={item}>{item}</option>)}</select></label><label>预算（元）<input type="number" min="0" value={project.budget} onChange={(event) => onUpdateProject({ budget: Number(event.target.value) })} /></label><label>计划完成日期<input type="date" value={project.dueDate} onChange={(event) => onUpdateProject({ dueDate: event.target.value })} /></label></section><section className="module-section api-status-card"><div><span className="section-kicker">API Runtime</span><h3>生成接口</h3><p>{backendStatus === "online" ? (providerInfo?.mode === "remote" ? "已配置外部生成平台，提交镜头后由服务端创建并轮询任务。" : "当前使用本地演示生成器；配置 .env 后会自动切换到外部平台。") : "FastAPI 未连接，生成任务无法同步到服务端。"}</p></div><span className={`status-pill ${backendStatus === "online" ? "success" : "muted"}`}>{providerLabel}</span></section></div>;
}

export function ModulePage({ activeNav, project, stats, actions }) {
  if (activeNav === "Agent") return <AgentPage project={project} stats={stats} actions={actions} />;
  if (activeNav === "概览") return <OverviewPage project={project} stats={stats} onNavigate={actions.navigate} />;
  if (activeNav === "故事") return <ScriptPage project={project} actions={actions} />;
  if (activeNav === "剧集") return <EpisodesPage project={project} onOpenEpisode={actions.openEpisode} />;
  if (activeNav === "素材库") return <AssetsPage project={project} onAddAsset={actions.addAsset} onUpdateAsset={actions.updateAsset} />;
  if (activeNav === "生成") return <GenerationPage project={project} onRetry={actions.retryTask} onCancel={actions.cancelTask} onNavigate={actions.navigate} />;
  if (activeNav === "时间线") return <TimelinePage project={project} />;
  if (activeNav === "质检") return <QCPage project={project} onReviewShot={actions.reviewShot} onRegenerate={actions.regenerateShot} />;
  if (activeNav === "导出") return <ExportPage project={project} onExport={actions.exportProject} />;
  return <SettingsPage project={project} onUpdateProject={actions.updateProject} backendStatus={actions.backendStatus} providerInfo={actions.providerInfo} />;
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
