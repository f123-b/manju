import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowRight, ArrowsOut, FilmStrip, Hand, Images, LinkSimple, Minus, Play, Plus, Robot, SpeakerHigh, Sparkle, Trash, X } from "@phosphor-icons/react";

const NODE_TYPES = [
  { type: "text", label: "文本", tone: "violet", hint: "灵感、规则、对白" },
  { type: "script", label: "脚本", tone: "amber", hint: "场景与节拍" },
  { type: "image", label: "图片", tone: "pink", hint: "角色、场景、镜头" },
  { type: "video", label: "视频", tone: "cyan", hint: "图生视频 / 镜头" },
  { type: "audio", label: "音频", tone: "slate", hint: "对白、配乐、音效" },
  { type: "agent", label: "Agent", tone: "blue", hint: "理解上下文并执行" },
];

const seedNode = (type) => ({
  type,
  title: NODE_TYPES.find((item) => item.type === type)?.label || "新节点",
  x: 180,
  y: 160,
  data: { content: "", prompt: "" },
});

function nodeType(type) {
  return NODE_TYPES.find((item) => item.type === type) || { type, label: type, tone: "slate", hint: "" };
}

function statusLabel(status) {
  return { idle: "待执行", queued: "排队中", running: "生成中", success: "已完成", failed: "失败" }[status] || status || "待执行";
}

function CanvasNode({ node, selected, connecting, linkMode, linkTarget, onSelect, onDragStart, onConnectStart, onConnectTarget, onRun, onDelete }) {
  const meta = nodeType(node.type);
  const preview = node.data?.outputUrl || node.data?.image || node.data?.thumbnail;
  const body = node.data?.content || node.data?.prompt || meta.hint;
  return <article className={`canvas-node tone-${meta.tone} ${selected ? "is-selected" : ""} ${connecting ? "is-connecting" : ""} ${linkMode ? "is-link-mode" : ""} ${linkTarget ? "is-link-target" : ""}`} style={{ left: node.x, top: node.y, width: node.width || 280, minHeight: node.height || 180 }} onPointerDown={(event) => { event.stopPropagation(); if (event.target.closest?.("button")) return; linkMode ? onDragStart(event, node) : onSelect(node.id); }}>
    <button className="canvas-port input" type="button" title={`输入端口：连接到${node.title}`} aria-label={`连接到${node.title}的输入端口`} onClick={(event) => { event.stopPropagation(); onConnectTarget(node.id); }} />
    <button className="canvas-port output" type="button" title={`输出端口：从${node.title}开始连接`} aria-label={`从${node.title}的输出端口开始连接`} onClick={(event) => { event.stopPropagation(); onConnectStart(node.id); }} />
    <header className="canvas-node-header" onPointerDown={(event) => { event.stopPropagation(); onDragStart(event, node); }}>
      <span className="canvas-node-icon">{node.type === "agent" ? <Robot size={16} /> : node.type === "video" ? <FilmStrip size={16} /> : node.type === "audio" ? <SpeakerHigh size={16} /> : node.type === "image" ? <Images size={16} /> : node.type === "script" ? <ArrowRight size={16} /> : "T"}</span>
      <strong>{node.title}</strong>
      <span className={`canvas-node-status ${node.status}`}>{statusLabel(node.status)}</span>
      <button className="canvas-node-menu" type="button" aria-label={`${node.title}删除`} onClick={(event) => { event.stopPropagation(); onDelete(node.id); }}><Trash size={14} /></button>
    </header>
    <div className="canvas-node-body">
      {preview ? <img src={preview} alt="" /> : <p>{body}</p>}
      {(node.data?.model || node.data?.shotId || node.data?.assetId) && <small>{node.data.model || node.data.shotId || node.data.assetId}</small>}
    </div>
    <footer className="canvas-node-footer"><span>{node.type === "agent" ? "上下文 → 结构化输出" : node.type === "image" ? "Prompt → Image" : node.type === "video" ? "Image → Video" : "可连接到下游节点"}</span>{["agent", "image", "video"].includes(node.type) && <button type="button" onClick={(event) => { event.stopPropagation(); onRun(node); }}><Play size={13} weight="fill" />运行</button>}</footer>
  </article>;
}

function CanvasInspector({ node, edge, edges, nodes, episodes, onChange, onCloseEdge, onSave, onRun, onDelete, onDeleteEdge }) {
  if (!node && edge) {
    const source = nodes.find((item) => item.id === edge.source);
    const target = nodes.find((item) => item.id === edge.target);
    return <aside className="canvas-inspector"><div className="canvas-inspector-top"><div><span className="canvas-kicker tone-blue">WORKFLOW LINK</span><h2>连接详情</h2></div><button type="button" aria-label="关闭连接检查器" onClick={onCloseEdge}><X size={17} /></button></div>
      <div className="canvas-edge-summary"><strong>{source?.title || edge.source}</strong><ArrowRight size={15} /><strong>{target?.title || edge.target}</strong></div>
      <p className="canvas-edge-copy">这条连接会把上游节点的输出传递给下游节点。点击画布中的连线可以再次打开这里。</p>
      {edge.label && <div className="canvas-edge-label"><span>连接标签</span><strong>{edge.label}</strong></div>}
      <button className="canvas-danger-action" type="button" onClick={() => onDeleteEdge(edge.id)}><X size={14} />删除这条连接</button>
    </aside>;
  }
  if (!node) return <aside className="canvas-inspector empty"><span className="canvas-inspector-mark">+</span><strong>选择一个节点</strong><p>编辑提示词、绑定镜头或运行工作流。</p></aside>;
  const meta = nodeType(node.type);
  const updateData = (key, value) => onChange({ ...node, data: { ...node.data, [key]: value } });
  const related = edges.filter((edge) => edge.source === node.id || edge.target === node.id);
  return <aside className="canvas-inspector"><div className="canvas-inspector-top"><div><span className={`canvas-kicker tone-${meta.tone}`}>{meta.label}</span><h2>{node.title}</h2></div><button type="button" aria-label="关闭节点检查器" onClick={() => onChange(null)}><X size={17} /></button></div>
    <label>节点名称<input value={node.title} onChange={(event) => onChange({ ...node, title: event.target.value })} /></label>
    <label>内容 / 提示词<textarea value={node.data?.content || node.data?.prompt || ""} onChange={(event) => updateData(node.data?.prompt ? "prompt" : "content", event.target.value)} placeholder="输入这个节点要传递给下游的内容…" /></label>
    {node.type === "agent" && <label>工作剧集<select value={node.data?.episodeId || ""} onChange={(event) => updateData("episodeId", event.target.value)}><option value="">跟随当前剧集</option>{episodes.map((episode) => <option key={episode.id} value={episode.id}>{episode.id} · {episode.title}</option>)}</select></label>}
    {node.type === "image" && <><label>资产类型<select value={node.data?.assetType || "locations"} onChange={(event) => updateData("assetType", event.target.value)}><option value="characters">角色</option><option value="locations">场景</option><option value="props">道具</option></select></label><label>资产 ID<input value={node.data?.assetId || ""} onChange={(event) => updateData("assetId", event.target.value)} placeholder="例如 C001 / L001" /></label></>}
    {node.type === "video" && <label>镜头 ID<input value={node.data?.shotId || ""} onChange={(event) => updateData("shotId", event.target.value)} placeholder="例如 SH041" /></label>}
    <div className="canvas-inspector-actions"><button className="primary-action" type="button" onClick={() => onSave(node)}>保存节点</button>{["agent", "image", "video"].includes(node.type) && <button type="button" onClick={() => onRun(node)}><Play size={14} weight="fill" />运行</button>}</div>
    <section className="canvas-connections"><div className="canvas-inspector-section-title"><strong>连接</strong><span>{related.length}</span></div>{related.length ? related.map((edge) => { const otherId = edge.source === node.id ? edge.target : edge.source; const other = nodes.find((item) => item.id === otherId); return <div className="canvas-connection-row" key={edge.id}><LinkSimple size={14} /><span>{edge.source === node.id ? "输出 →" : "← 输入"} {other?.title || otherId}{edge.label ? ` · ${edge.label}` : ""}</span><button type="button" onClick={() => onDeleteEdge(edge.id)}><X size={13} /></button></div>; }) : <small>点击“连接节点”后点两个节点，或直接使用节点两侧端口来连线。</small>}</section>
    <button className="canvas-danger-action" type="button" onClick={() => onDelete(node.id)}><Trash size={14} />删除节点</button>
  </aside>;
}

export function CanvasPage({ project, actions }) {
  const [canvas, setCanvas] = useState({ nodes: [], edges: [] });
  const [selectedId, setSelectedId] = useState(null);
  const [connectingId, setConnectingId] = useState(null);
  const [connectionMode, setConnectionMode] = useState(false);
  const [selectedEdgeId, setSelectedEdgeId] = useState(null);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [zoom, setZoom] = useState(0.82);
  const [pan, setPan] = useState({ x: 32, y: 28 });
  const [drag, setDrag] = useState(null);
  const surfaceRef = useRef(null);

  useEffect(() => {
    if (actions.backendStatus !== "online") return;
    actions.getCanvas().then((next) => setCanvas(next)).catch((error) => actions.notify?.(error?.message || "画布读取失败", "error"));
  }, [actions.backendStatus]);

  const selectedNode = canvas.nodes.find((node) => node.id === selectedId) || null;
  const selectedEdge = canvas.edges.find((edge) => edge.id === selectedEdgeId) || null;
  const nodeMap = useMemo(() => new Map(canvas.nodes.map((node) => [node.id, node])), [canvas.nodes]);

  const saveNode = async (node) => {
    const next = await actions.patchCanvasNode(node.id, { title: node.title, data: node.data, status: node.status });
    setCanvas((current) => ({ ...current, nodes: current.nodes.map((item) => item.id === next.id ? next : item) }));
    actions.notify?.("画布节点已保存");
  };

  const addNode = async (type) => {
    const draft = seedNode(type);
    draft.x = 160 + (canvas.nodes.length % 3) * 320;
    draft.y = 140 + Math.floor(canvas.nodes.length / 3) * 290;
    try {
      const node = await actions.createCanvasNode(draft);
      setCanvas((current) => ({ ...current, nodes: [...current.nodes, node] }));
      setSelectedId(node.id);
      setPaletteOpen(false);
    } catch (error) { actions.notify?.(error?.message || "节点创建失败", "error"); }
  };

  const handlePointerDown = (event, node) => {
    if (connectionMode) {
      if (connectingId) finishConnect(node.id);
      else startConnect(node.id);
      return;
    }
    setSelectedEdgeId(null);
    setDrag({ id: node.id, startX: event.clientX, startY: event.clientY, originX: node.x, originY: node.y });
  };
  const handlePointerMove = (event) => {
    if (!drag) return;
    const dx = (event.clientX - drag.startX) / zoom;
    const dy = (event.clientY - drag.startY) / zoom;
    setCanvas((current) => ({ ...current, nodes: current.nodes.map((item) => item.id === drag.id ? { ...item, x: Math.max(20, drag.originX + dx), y: Math.max(20, drag.originY + dy) } : item) }));
  };
  const handlePointerUp = async () => {
    if (!drag) return;
    const moved = canvas.nodes.find((node) => node.id === drag.id);
    setDrag(null);
    if (moved) await actions.patchCanvasNode(moved.id, { x: moved.x, y: moved.y }).catch(() => {});
  };
  const startConnect = (nodeId) => { setConnectionMode(true); setConnectingId(nodeId); setSelectedId(nodeId); setSelectedEdgeId(null); actions.notify?.("已选择起点，请点击目标节点或它左侧的输入端口"); };
  const finishConnect = async (targetId) => {
    if (!connectingId) { actions.notify?.("请先选择一个起点"); return; }
    if (connectingId === targetId) { actions.notify?.("不能把节点连接到自身"); return; }
    const source = nodeMap.get(connectingId);
    const target = nodeMap.get(targetId);
    try {
      const edge = await actions.createCanvasEdge({ source: connectingId, target: targetId, label: `${source?.title || connectingId} → ${target?.title || targetId}` });
      setCanvas((current) => ({ ...current, edges: [...current.edges, edge] }));
      setSelectedId(targetId);
      setSelectedEdgeId(null);
      actions.notify?.("节点连接已创建，可以继续选择下一个起点");
    } catch (error) { actions.notify?.(error?.message || "节点连接失败", "error"); }
    setConnectingId(null);
  };
  const deleteNode = async (nodeId) => {
    await actions.deleteCanvasNode(nodeId);
    setCanvas((current) => ({ nodes: current.nodes.filter((node) => node.id !== nodeId), edges: current.edges.filter((edge) => edge.source !== nodeId && edge.target !== nodeId) }));
    if (selectedId === nodeId) setSelectedId(null);
  };
  const deleteEdge = async (edgeId) => {
    await actions.deleteCanvasEdge(edgeId);
    setCanvas((current) => ({ ...current, edges: current.edges.filter((edge) => edge.id !== edgeId) }));
    if (selectedEdgeId === edgeId) setSelectedEdgeId(null);
  };
  const toggleConnectionMode = () => {
    if (connectionMode) {
      setConnectionMode(false);
      setConnectingId(null);
      actions.notify?.("已退出连接模式");
    } else {
      setConnectionMode(true);
      setSelectedEdgeId(null);
      actions.notify?.("连接模式：点击一个节点作为起点，再点击目标节点");
    }
  };
  const runNode = async (node) => {
    try {
      const result = await actions.runCanvasNode(node.id, { data: node.data });
      setCanvas((current) => ({ ...current, nodes: current.nodes.map((item) => item.id === node.id ? { ...item, status: "queued" } : item) }));
      actions.notify?.(result.kind === "agent" ? "Agent 节点已进入执行队列" : "生成节点已进入任务中心");
    } catch (error) { actions.notify?.(error?.message || "节点执行失败", "error"); }
  };
  const pathFor = (edge) => {
    const source = nodeMap.get(edge.source);
    const target = nodeMap.get(edge.target);
    if (!source || !target) return "";
    const sx = source.x + (source.width || 280);
    const sy = source.y + (source.height || 180) / 2;
    const tx = target.x;
    const ty = target.y + (target.height || 180) / 2;
    const bend = Math.max(90, Math.abs(tx - sx) * 0.48);
    return `M ${sx} ${sy} C ${sx + bend} ${sy}, ${tx - bend} ${ty}, ${tx} ${ty}`;
  };

  return <div className="canvas-page">
    <header className="canvas-toolbar"><div className="canvas-toolbar-title"><span>INFINITE CANVAS</span><h1>生产画布</h1><p>把故事、资产、镜头和生成任务连成一条可执行工作流</p></div><div className="canvas-toolbar-actions"><button type="button" className={connectionMode ? "is-active" : ""} onClick={toggleConnectionMode}><LinkSimple size={16} />{connectionMode ? "退出连接" : "连接节点"}</button><div className="canvas-add-wrap"><button className="primary-action" type="button" onClick={() => setPaletteOpen((open) => !open)}><Plus size={17} />添加节点</button>{paletteOpen && <div className="canvas-node-palette">{NODE_TYPES.map((item) => <button type="button" key={item.type} onClick={() => addNode(item.type)}><i className={`palette-dot tone-${item.tone}`} /><span><strong>{item.label}</strong><small>{item.hint}</small></span></button>)}</div>}</div></div></header>
    <div className="canvas-workspace">
      <aside className="canvas-left-rail"><div className="canvas-rail-heading"><span>WORKFLOW</span><strong>{canvas.nodes.length} 节点</strong></div><div className="canvas-mini-map"><div className="mini-map-grid">{canvas.nodes.map((node) => <button type="button" key={node.id} className={`mini-map-node tone-${nodeType(node.type).tone} ${selectedId === node.id ? "is-selected" : ""}`} style={{ left: `${Math.min(88, Math.max(4, node.x / 16))}%`, top: `${Math.min(86, Math.max(4, node.y / 8))}%` }} onClick={() => setSelectedId(node.id)} aria-label={node.title} />)}</div></div><div className="canvas-rail-section"><span>当前项目</span><strong>{project.title}</strong><small>{project.currentEpisodeId} · {project.episodes.find((item) => item.id === project.currentEpisodeId)?.title}</small></div><div className="canvas-rail-section"><span>工作流建议</span><p><b>1</b>故事 → Agent → 脚本</p><p><b>2</b>参考资产 → 镜头 → 视频</p><p><b>3</b>视频与音频 → 时间线</p></div><button className="canvas-rail-help" type="button" onClick={() => actions.notify?.("双击节点端口可以建立上下游连接")}>使用提示 <ArrowRight size={14} /></button></aside>
      <section className={`canvas-surface ${connectionMode ? "is-linking" : ""}`} ref={surfaceRef} onPointerMove={handlePointerMove} onPointerUp={handlePointerUp} onPointerLeave={handlePointerUp} onPointerDown={(event) => { if (event.target === event.currentTarget) { setSelectedId(null); setSelectedEdgeId(null); if (connectingId) setConnectingId(null); } }}>
        <div className="canvas-surface-tools"><button type="button" onClick={() => setZoom((value) => Math.min(1.35, value + 0.1))}><Plus size={15} /></button><span>{Math.round(zoom * 100)}%</span><button type="button" onClick={() => setZoom((value) => Math.max(0.5, value - 0.1))}><Minus size={15} /></button><i /><button type="button" onClick={() => { setPan({ x: 32, y: 28 }); setZoom(0.82); }}><ArrowsOut size={15} /></button><button type="button" className="hand-tool"><Hand size={15} /></button></div>
        <div className="canvas-scene" style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})` }}><svg className="canvas-edges" width="1800" height="1200"><defs><linearGradient id="canvas-edge-gradient" x1="0" x2="1"><stop offset="0" stopColor="#8cb7ff" /><stop offset="1" stopColor="#5a80f6" /></linearGradient><marker id="canvas-edge-arrow" markerWidth="9" markerHeight="9" refX="7" refY="4" orient="auto" markerUnits="strokeWidth"><path d="M 0 0 L 8 4 L 0 8 z" fill="#5a80f6" /></marker></defs>{canvas.edges.map((edge) => { const source = nodeMap.get(edge.source); const target = nodeMap.get(edge.target); return <path key={edge.id} d={pathFor(edge)} className={`canvas-edge-path ${selectedEdgeId === edge.id ? "is-selected" : ""}`} markerEnd="url(#canvas-edge-arrow)" role="button" tabIndex="0" aria-label={`${source?.title || edge.source}连接到${target?.title || edge.target}`} onPointerDown={(event) => { event.stopPropagation(); setSelectedId(null); setSelectedEdgeId(edge.id); }} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setSelectedId(null); setSelectedEdgeId(edge.id); } }} />; })}</svg>{canvas.nodes.map((node) => <CanvasNode key={node.id} node={node} selected={selectedId === node.id} connecting={connectingId === node.id} linkMode={connectionMode} linkTarget={connectionMode && Boolean(connectingId) && connectingId !== node.id} onSelect={(nodeId) => { setSelectedId(nodeId); setSelectedEdgeId(null); }} onDragStart={handlePointerDown} onConnectStart={startConnect} onConnectTarget={finishConnect} onRun={runNode} onDelete={deleteNode} />)}</div>
        {connectionMode && <div className="canvas-linking-hint"><LinkSimple size={15} />{connectingId ? `正在从「${canvas.nodes.find((node) => node.id === connectingId)?.title}」连接到目标节点` : "连接模式：点击一个节点作为起点"}</div>}
        {!canvas.nodes.length && <div className="canvas-empty"><Sparkle size={28} /><strong>开始搭建你的生产画布</strong><p>添加文本、Agent、图片和视频节点，连线后就能沿着工作流执行。</p><button className="primary-action" type="button" onClick={() => addNode("text")}><Plus size={16} />添加第一个节点</button></div>}
      </section>
      <CanvasInspector node={selectedNode} edge={selectedEdge} edges={canvas.edges} nodes={canvas.nodes} episodes={project.episodes || []} onChange={(node) => { setSelectedId(node?.id || null); setSelectedEdgeId(null); }} onCloseEdge={() => setSelectedEdgeId(null)} onSave={saveNode} onRun={runNode} onDelete={deleteNode} onDeleteEdge={deleteEdge} />
    </div>
  </div>;
}
