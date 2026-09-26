import { useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  ArrowsOutSimple,
  CaretDown,
  CaretRight,
  Check,
  CheckCircle,
  Copy,
  DotsThree,
  FileText,
  GearSix,
  Pause,
  Play,
  Plus,
  SpeakerHigh,
  Sparkle,
  Trash,
  CopySimple,
} from "@phosphor-icons/react";

const inspectorTabs = ["镜头设置", "角色", "场景", "风格", "其他"];
const previewTabs = ["分镜画面", "故事板", "对白/字幕", "参考图", "历史版本"];

const settingOptions = {
  frame: ["16:9（横屏）", "9:16（竖屏）", "1:1（方形）"],
  lens: ["85mm（中长焦，人物特写）", "50mm（标准镜头）", "35mm（环境人像）"],
  angle: ["平视", "低机位", "高机位"],
  movement: ["微推（Slow Push In）", "固定镜头", "缓慢拉远", "跟拍"],
};

const settingLabels = {
  frame: "画面尺寸",
  lens: "镜头焦段",
  angle: "机位角度",
  movement: "镜头运动",
};

function secondsLabel(value) {
  return `00:${String(Math.floor(value)).padStart(2, "0")}`;
}

function ShotRail({ project, shots, selectedShot, onSelect, onAdd, onEpisodeChange }) {
  const episodeIndex = project.episodes.findIndex((episode) => episode.id === project.currentEpisodeId);
  const currentEpisode = project.episodes[episodeIndex];
  const goEpisode = (offset) => {
    const next = project.episodes[episodeIndex + offset];
    if (next) onEpisodeChange(next.id);
  };

  return (
    <section className="shot-rail" aria-label="镜头列表">
      <div className="episode-select-row">
        <button className="square-button" type="button" aria-label="上一集" disabled={episodeIndex <= 0} onClick={() => goEpisode(-1)}><ArrowLeft size={18} /></button>
        <label className="episode-select episode-select-native">
          <select value={project.currentEpisodeId} onChange={(event) => onEpisodeChange(event.target.value)} aria-label="选择剧集">
            {project.episodes.map((episode) => <option key={episode.id} value={episode.id}>{episode.id}　{episode.title}</option>)}
          </select>
          <CaretDown size={15} />
        </label>
        <button className="square-button" type="button" aria-label="下一集" disabled={episodeIndex >= project.episodes.length - 1} onClick={() => goEpisode(1)}><ArrowRight size={18} /></button>
      </div>
      <div className="scene-heading">
        <div><strong>场景 {project.currentScene.number}</strong><span>{project.currentScene.title}</span></div>
        <div className="scene-actions"><span>{shots.length} 个镜头</span><DotsThree size={21} weight="bold" /></div>
      </div>
      <div className="shot-list">
        {shots.length ? shots.map((shot) => (
          <button className={`shot-row ${selectedShot?.id === shot.id ? "is-selected" : ""}`} key={shot.id} onClick={() => onSelect(shot.id)} type="button">
            <img src={shot.image} alt="" />
            <span className="shot-copy">
              <span className="shot-title-row"><strong>{shot.id}</strong><i className={`shot-status ${shot.status}`} /></span>
              <small>{shot.time}</small>
              <em>{shot.description}</em>
              <span className="shot-tags"><i>{shot.size}</i><i>{shot.duration}s</i></span>
            </span>
          </button>
        )) : <div className="shot-empty"><strong>{currentEpisode?.id} 还没有镜头</strong><span>添加第一个镜头开始制作。</span></div>}
      </div>
      <button className="add-shot" type="button" onClick={onAdd}><Plus size={18} />添加镜头</button>
      <div className="rail-footer">
        <div className="rail-footer-top"><span>项目用量</span><strong>{Math.round(project.spent / project.budget * 100)}%</strong></div>
        <div className="rail-usage-track"><span style={{ width: `${Math.min(100, project.spent / project.budget * 100)}%` }} /></div>
        <div className="rail-footer-values"><span>已用<strong>¥{project.spent.toFixed(2)}</strong></span><span>总预算<strong>¥{project.budget.toFixed(2)}</strong></span></div>
        <button className="rail-settings" type="button"><GearSix size={17} />项目设置</button>
      </div>
    </section>
  );
}

function PreviewPanel({ project, shots, selectedShot, onSelect, onUpdateShot, onDuplicate, onDelete }) {
  const [activeTab, setActiveTab] = useState("分镜画面");
  const [isPlaying, setIsPlaying] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    setElapsed(0);
    setIsPlaying(false);
  }, [selectedShot?.id]);

  useEffect(() => {
    if (!isPlaying || !selectedShot) return undefined;
    const timer = window.setInterval(() => {
      setElapsed((current) => {
        const next = current + 0.1;
        if (next >= selectedShot.duration) {
          setIsPlaying(false);
          return 0;
        }
        return next;
      });
    }, 100);
    return () => window.clearInterval(timer);
  }, [isPlaying, selectedShot]);

  if (!selectedShot) {
    return <section className="preview-panel empty-workspace"><strong>当前剧集还没有镜头</strong><p>从左侧添加镜头后即可开始分镜制作。</p></section>;
  }

  const toggleReviewed = () => onUpdateShot(selectedShot.id, { reviewed: !selectedShot.reviewed });
  const progress = selectedShot.duration ? elapsed / selectedShot.duration * 100 : 0;

  return (
    <section className="preview-panel">
      <div className="workspace-toolbar">
        <h1>{selectedShot.id}</h1>
        <div className="workspace-actions">
          <button className={`review-button ${selectedShot.reviewed ? "is-reviewed" : ""}`} type="button" onClick={toggleReviewed}>{selectedShot.reviewed ? <CheckCircle size={17} weight="fill" /> : <Check size={17} weight="bold" />}{selectedShot.reviewed ? "已标记审核" : "标记已审核"}</button>
          <div className="shot-menu-wrap">
            <button className="plain-icon-button" type="button" aria-label="更多镜头选项" onClick={() => setMenuOpen((open) => !open)}><DotsThree size={23} weight="bold" /></button>
            {menuOpen && <div className="shot-menu"><button type="button" onClick={() => { onDuplicate(selectedShot.id); setMenuOpen(false); }}><CopySimple size={16} />复制镜头</button><button className="danger" type="button" onClick={() => { onDelete(selectedShot.id); setMenuOpen(false); }}><Trash size={16} />删除镜头</button></div>}
          </div>
        </div>
      </div>
      <div className="preview-frame"><img src={selectedShot.image} alt={`${selectedShot.id} 画面预览`} /><div className="preview-subtitle">{selectedShot.dialogue}</div></div>
      <div className="player-controls">
        <button className="play-button" type="button" onClick={() => setIsPlaying((value) => !value)} aria-label={isPlaying ? "暂停预览" : "播放预览"}>{isPlaying ? <Pause size={17} weight="fill" /> : <Play size={18} weight="fill" />}</button>
        <span className="player-time">{secondsLabel(elapsed)} / {secondsLabel(selectedShot.duration)}</span>
        <div className="scrubber" aria-label="播放进度"><span style={{ width: `${progress}%` }} /><i style={{ left: `${progress}%` }} /></div>
        <button className="plain-icon-button" type="button" aria-label="音量"><SpeakerHigh size={20} /></button>
        <button className="quality-select" type="button">1080P <CaretDown size={13} /></button>
        <button className="plain-icon-button" type="button" aria-label="全屏"><ArrowsOutSimple size={20} /></button>
      </div>
      <div className="preview-tabs" role="tablist" aria-label="镜头详情">
        {previewTabs.map((tab) => <button className={activeTab === tab ? "is-active" : ""} key={tab} type="button" role="tab" aria-selected={activeTab === tab} onClick={() => setActiveTab(tab)}>{tab}{tab === "历史版本" ? `（${selectedShot.versions.length}）` : ""}</button>)}
      </div>
      <div className="preview-tab-content">
        {activeTab === "分镜画面" && <div className="storyboard-strip">{shots.slice(0, 4).map((shot, index) => <button className={shot.id === selectedShot.id ? "is-current" : ""} key={`${shot.id}-strip`} type="button" onClick={() => onSelect(shot.id)}><span>{String(index + 1).padStart(2, "0")}</span><img src={shot.image} alt="" /><small>{shot.description}</small></button>)}</div>}
        {activeTab === "故事板" && <div className="storyboard-list">{shots.map((shot, index) => <button type="button" key={shot.id} onClick={() => onSelect(shot.id)}><span>{index + 1}</span><img src={shot.image} alt="" /><strong>{shot.id}</strong><em>{shot.description}</em><small>{shot.duration}s</small></button>)}</div>}
        {activeTab === "对白/字幕" && <div className="inline-editor"><label htmlFor="dialogue">对白 / 字幕</label><textarea id="dialogue" value={selectedShot.dialogue} onChange={(event) => onUpdateShot(selectedShot.id, { dialogue: event.target.value })} /><p>修改后会自动保存到当前镜头。</p></div>}
        {activeTab === "参考图" && <div className="reference-grid">{project.assets.characters.map((item) => <button key={item.id} type="button"><img src={item.image} alt="" /><strong>{item.name}</strong><span>{item.meta}</span></button>)}<button type="button"><img src={project.assets.locations[0].image} alt="" /><strong>{project.assets.locations[0].name}</strong><span>{project.assets.locations[0].meta}</span></button></div>}
        {activeTab === "历史版本" && <div className="version-list">{selectedShot.versions.length ? selectedShot.versions.map((version) => <div key={version.id}><span>{version.id}</span><strong>{version.active ? "当前版本" : "历史版本"}</strong><small>{version.createdAt}</small></div>) : <p>这个镜头还没有生成版本。</p>}</div>}
      </div>
      <article className="scene-note"><div className="scene-note-title"><FileText size={17} /><strong>本场景剧情要点</strong><span>{project.currentScene.title}</span></div><p>{project.currentScene.purpose}</p></article>
    </section>
  );
}

function RoleCard({ item, selected, onToggle }) {
  return <button className={`role-card ${selected ? "is-selected" : ""}`} type="button" onClick={onToggle}><img src={item.image} alt="" /><span><strong>{item.name}</strong><small>{item.meta}</small></span>{selected ? <CheckCircle size={17} weight="fill" /> : <CaretRight size={17} />}</button>;
}

function Inspector({ project, selectedShot, onUpdateShot, onUpdateScene, onGenerate }) {
  const [activeTab, setActiveTab] = useState("镜头设置");
  const [copied, setCopied] = useState(false);
  const characters = project.assets.characters;

  useEffect(() => setActiveTab("镜头设置"), [selectedShot?.id]);

  if (!selectedShot) return <aside className="inspector empty-inspector"><strong>等待镜头</strong><p>添加镜头后可编辑参数。</p></aside>;

  const copyPrompt = async () => {
    try { await navigator.clipboard?.writeText(selectedShot.prompt); } catch { /* Clipboard may be unavailable. */ }
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1200);
  };

  const toggleCharacter = (characterId) => {
    const current = selectedShot.characterIds || [];
    const next = current.includes(characterId) ? current.filter((id) => id !== characterId) : [...current, characterId];
    onUpdateShot(selectedShot.id, { characterIds: next });
  };

  return (
    <aside className="inspector">
      <div className="inspector-tabs" role="tablist" aria-label="镜头检查器">{inspectorTabs.map((tab) => <button className={activeTab === tab ? "is-active" : ""} key={tab} onClick={() => setActiveTab(tab)} type="button" role="tab" aria-selected={activeTab === tab}>{tab}</button>)}</div>
      <div className="inspector-scroll">
        {activeTab === "镜头设置" && <>
          <div className="section-block first-block"><div className="detail-row"><span>镜头编号</span><strong>{selectedShot.id}</strong></div><div className="detail-row"><span>所属剧集</span><strong>{selectedShot.episodeId}</strong></div><div className="detail-row"><span>所属场景</span><strong>场景 {project.currentScene.number}　{project.currentScene.title}</strong></div><div className="detail-row"><span>镜头状态</span><strong className={`text-status ${selectedShot.status}`}>{selectedShot.status}</strong></div></div>
          <div className="section-block"><h2>画面设置</h2>{Object.entries(settingOptions).map(([field, options]) => <label className="select-row select-row-native" key={field}><span>{settingLabels[field]}</span><select value={selectedShot[field]} onChange={(event) => onUpdateShot(selectedShot.id, { [field]: event.target.value })}>{options.map((option) => <option key={option}>{option}</option>)}</select><CaretDown size={15} /></label>)}</div>
          <div className="section-block"><h2>基础信息</h2><label className="field-label">镜头描述<input value={selectedShot.description} onChange={(event) => onUpdateShot(selectedShot.id, { description: event.target.value })} /></label><label className="field-label">景别<select value={selectedShot.size} onChange={(event) => onUpdateShot(selectedShot.id, { size: event.target.value })}>{["远景", "全景", "中景", "近景", "特写"].map((item) => <option key={item}>{item}</option>)}</select></label><label className="field-label">时长（秒）<input type="number" min="1" max="15" value={selectedShot.duration} onChange={(event) => onUpdateShot(selectedShot.id, { duration: Number(event.target.value) })} /></label></div>
        </>}

        {activeTab === "角色" && <>
          <div className="section-block first-block"><h2>出现角色</h2><div className="role-grid">{characters.map((character) => <RoleCard key={character.id} item={character} selected={selectedShot.characterIds.includes(character.id)} onToggle={() => toggleCharacter(character.id)} />)}</div></div>
          <div className="section-block"><h2>服装造型</h2><div className="outfit-grid"><button className={`outfit-card ${selectedShot.outfitId === "O001" ? "is-selected" : ""}`} onClick={() => onUpdateShot(selectedShot.id, { outfitId: "O001" })} type="button"><img src="/assets/shot-hero.png" alt="" /><span>黑色高领毛衣 +<br />风衣</span></button><button className={`outfit-card ${selectedShot.outfitId === "O002" ? "is-selected" : ""}`} onClick={() => onUpdateShot(selectedShot.id, { outfitId: "O002" })} type="button"><img src="/assets/shot-woman.png" alt="" /><span>白色针织衫</span></button></div></div>
        </>}

        {activeTab === "场景" && <div className="section-block first-block"><h2>场景信息</h2><label className="field-label">场景名称<input value={project.currentScene.title} onChange={(event) => onUpdateScene({ title: event.target.value })} /></label><label className="field-label">剧情目的<textarea value={project.currentScene.purpose} onChange={(event) => onUpdateScene({ purpose: event.target.value })} /></label><div className="location-card"><img src={project.assets.locations[0].image} alt="" /><span><strong>{project.assets.locations[0].name}</strong><small>{project.assets.locations[0].meta}</small></span></div></div>}

        {activeTab === "风格" && <div className="section-block first-block prompt-block"><div className="prompt-heading"><h2>生成提示词（Prompt）</h2><button type="button" onClick={copyPrompt}><Copy size={15} />{copied ? "已复制" : "复制"}</button></div><textarea value={selectedShot.prompt} onChange={(event) => onUpdateShot(selectedShot.id, { prompt: event.target.value })} aria-label="生成提示词" /><div className="prompt-tags">{["电影质感", "写实风格", "夜景", "情感张力", "8k"].map((tag) => <span key={tag}>{tag}</span>)}</div></div>}

        {activeTab === "其他" && <div className="section-block first-block"><h2>对白与审核</h2><label className="field-label">对白 / 字幕<textarea value={selectedShot.dialogue} onChange={(event) => onUpdateShot(selectedShot.id, { dialogue: event.target.value })} /></label><label className="field-label">生产状态<select value={selectedShot.status} onChange={(event) => onUpdateShot(selectedShot.id, { status: event.target.value })}>{["待生成", "生成中", "已生成", "失败"].map((status) => <option key={status}>{status}</option>)}</select></label><label className="check-field"><input type="checkbox" checked={selectedShot.reviewed} onChange={(event) => onUpdateShot(selectedShot.id, { reviewed: event.target.checked })} />已人工审核</label></div>}
      </div>
      <div className="inspector-footer"><div className="estimate"><span>已消耗</span><strong>¥{selectedShot.cost.toFixed(2)}</strong></div><div className="quality-estimate"><span>质检得分</span><strong>{selectedShot.qcScore ?? "--"}{selectedShot.qcScore ? "%" : ""}</strong></div><button className="generate-button" type="button" disabled={selectedShot.status === "生成中"} onClick={() => onGenerate(selectedShot.id, selectedShot.prompt)}><Sparkle size={18} weight="fill" />{selectedShot.status === "生成中" ? "生成中…" : "生成此镜头"}<ArrowRight size={18} /></button></div>
    </aside>
  );
}

export function StoryboardWorkspace({ project, selectedShotId, onSelectShot, onAddShot, onDuplicateShot, onDeleteShot, onUpdateShot, onUpdateScene, onGenerate, onEpisodeChange }) {
  const shots = useMemo(() => project.shots.filter((shot) => shot.episodeId === project.currentEpisodeId), [project.shots, project.currentEpisodeId]);
  const selectedShot = shots.find((shot) => shot.id === selectedShotId) || shots[0] || null;

  useEffect(() => {
    if (selectedShot && selectedShot.id !== selectedShotId) onSelectShot(selectedShot.id);
  }, [selectedShot, selectedShotId, onSelectShot]);

  return (
    <div className="storyboard-layout">
      <ShotRail project={project} shots={shots} selectedShot={selectedShot} onSelect={onSelectShot} onAdd={onAddShot} onEpisodeChange={onEpisodeChange} />
      <PreviewPanel project={project} shots={shots} selectedShot={selectedShot} onSelect={onSelectShot} onUpdateShot={onUpdateShot} onDuplicate={onDuplicateShot} onDelete={onDeleteShot} />
      <Inspector project={project} selectedShot={selectedShot} onUpdateShot={onUpdateShot} onUpdateScene={onUpdateScene} onGenerate={onGenerate} />
    </div>
  );
}
