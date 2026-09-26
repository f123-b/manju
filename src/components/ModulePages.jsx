import { useMemo, useState } from "react";
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
  Sparkle,
  Trash,
  Warning,
  X,
} from "@phosphor-icons/react";

function PageHeader({ eyebrow, title, description, action }) {
  return <div className="module-header"><div><span>{eyebrow}</span><h1>{title}</h1><p>{description}</p></div>{action}</div>;
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
  if (activeNav === "概览") return <OverviewPage project={project} stats={stats} onNavigate={actions.navigate} />;
  if (activeNav === "故事") return <StoryPage project={project} onUpdateStory={actions.updateStory} onAddRule={actions.addRule} onRemoveRule={actions.removeRule} />;
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
