import {
  Bell,
  CaretDown,
  CheckCircle,
  Clock,
  Export,
  FilmSlate,
  FilmStrip,
  GearSix,
  Graph,
  House,
  Images,
  MagnifyingGlass,
  Note,
  Robot,
  Sparkle,
  SquaresFour,
  SpeakerHigh,
} from "@phosphor-icons/react";

const navItems = [
  { label: "Agent", icon: Robot },
  { label: "画布", icon: Graph },
  { label: "概览", icon: House },
  { label: "故事", icon: Note },
  { label: "剧集", icon: FilmStrip },
  { label: "素材库", icon: Images },
  { label: "生图", icon: Sparkle },
  { label: "分镜", icon: SquaresFour },
  { label: "生成", icon: Sparkle },
  { label: "声音", icon: SpeakerHigh },
  { label: "时间线", icon: Clock },
  { label: "质检", icon: CheckCircle },
  { label: "导出", icon: Export },
];

export function Sidebar({ activeNav, onNavigate }) {
  return (
    <aside className="sidebar">
      <button className="brand-lockup" type="button" aria-label="打开 Agent" onClick={() => onNavigate("Agent")}>
        <span className="brand-mark" aria-hidden="true"><FilmSlate size={21} weight="fill" /></span>
        <span><span className="brand-name">Short Drama OS</span><span className="brand-tagline">用 AI 讲好每一个故事</span></span>
      </button>
      <nav className="primary-nav" aria-label="主导航">
        {navItems.map(({ label, icon: Icon }) => (
          <button className={`nav-item ${activeNav === label ? "is-active" : ""}`} key={label} aria-label={label} onClick={() => onNavigate(label)} type="button">
            <Icon size={21} weight={activeNav === label ? "fill" : "regular"} />
            <span>{label}</span>
          </button>
        ))}
      </nav>
      <div className="sidebar-bottom">
        <button className="settings-link" type="button" onClick={() => onNavigate("设置")}><GearSix size={18} />设置</button>
      </div>
    </aside>
  );
}

export function Topbar({ project, onSearch }) {
  const currentEpisode = project.episodes.find((episode) => episode.id === project.currentEpisodeId);
  return (
    <header className="topbar">
      <div className="project-context">
        <span className="context-title">《{project.title}》</span>
        <CaretDown size={15} weight="bold" />
        <span className="status-pill">{project.status}</span>
        <span className="context-divider" />
        <span>共 {project.targetEpisodes} 集</span>
        <span className="context-divider" />
        <span>当前 {currentEpisode?.id || project.currentEpisodeId}</span>
        <span className="context-divider" />
        <span>预计完成 {project.dueDate}</span>
      </div>
      <div className="topbar-actions">
        <button className="icon-button" type="button" aria-label="搜索" onClick={onSearch}><MagnifyingGlass size={21} /></button>
        <button className="icon-button notification" type="button" aria-label="通知"><Bell size={21} /><i /></button>
        <div className="profile">
          <img src="/assets/shot-woman.png" alt="导演小北" />
          <div><strong>导演小北</strong><span>创作者</span></div>
          <CaretDown size={14} />
        </div>
      </div>
    </header>
  );
}
