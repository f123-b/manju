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
  data: type === "image" || type === "video" ? { prompt: "" } : { content: "" },
});

function nodeType(type) {
  return NODE_TYPES.find((item) => item.type === type) || { type, label: type, tone: "slate", hint: "" };
}

function statusLabel(status) {
  return { idle: "待执行", queued: "排队中", running: "生成中", success: "已完成", failed: "失败" }[status] || status || "待执行";
}

function CanvasNode({ node, selected, connecting, linkMode, linkTarget, connectionDrag, onSelect, onDragStart, onConnectStart, onConnectTarget, onConnectDragStart, onConnectDragEnd, onRun, onDelete }) {
  const meta = nodeType(node.type);
  const preview = node.data?.outputUrl || node.data?.image || node.data?.thumbnail;
  const body = node.data?.prompt || node.data?.content || meta.hint;
  return <article className={`canvas-node tone-${meta.tone} ${selected ? "is-selected" : ""} ${connecting ? "is-connecting" : ""} ${linkMode || connectionDrag ? "is-link-mode" : ""} ${linkTarget ? "is-link-target" : ""}`} data-canvas-node-id={node.id} style={{ left: node.x, top: node.y, width: node.width || 280, minHeight: node.height || 180 }} onPointerDown={(event) => { event.stopPropagation(); if (event.target.closest?.("button")) return; linkMode ? onDragStart(event, node) : onSelect(node.id); }} onPointerUp={(event) => { if (connectionDrag && node.id !== connectionDrag.sourceId) { event.stopPropagation(); onConnectDragEnd(event, node.id); } }}>
    <button className="canvas-port input" type="button" title={`拖到这里连接到${node.title}`} aria-label={`连接到${node.title}的输入端口`} onPointerUp={(event) => { event.stopPropagation(); onConnectDragEnd(event, node.id); }} onClick={(event) => { event.stopPropagation(); onConnectTarget(node.id); }} />
    <button className="canvas-port output" type="button" title={`从这里拖出连接带`} aria-label={`从${node.title}的输出端口拖出连接`} onPointerDown={(event) => { event.preventDefault(); event.stopPropagation(); onConnectDragStart(event, node.id); }} onClick={(event) => { event.stopPropagation(); onConnectStart(node.id); }} />
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
  const textKey = node.type === "image" || node.type === "video" ? "prompt" : "content";
  const textValue = node.data?.[textKey] ?? node.data?.content ?? node.data?.prompt ?? "";
  const updateData = (key, value) => onChange({ ...node, data: { ...node.data, [key]: value } });
  const related = edges.filter((edge) => edge.source === node.id || edge.target === node.id);
  return <aside className="canvas-inspector"><div className="canvas-inspector-top"><div><span className={`canvas-kicker tone-${meta.tone}`}>{meta.label}</span><h2>{node.title}</h2></div><button type="button" aria-label="关闭节点检查器" onClick={() => onChange(null)}><X size={17} /></button></div>
    <label>节点名称<input value={node.title} onChange={(event) => onChange({ ...node, title: event.target.value })} /></label>
    <label>{textKey === "prompt" ? "生成提示词" : "内容 / 提示词"}<textarea value={textValue} onChange={(event) => updateData(textKey, event.target.value)} placeholder="输入这个节点要传递给下游的内容…" /></label>
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
  const [viewportDrag, setViewportDrag] = useState(null);
  const [panMode, setPanMode] = useState(false);
  const [connectionDrag, setConnectionDrag] = useState(null);
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

  const findOpenPosition = () => {
    const width = 280;
    const height = 180;
    const gap = 36;
    for (let row = 0; row < 12; row += 1) {
      for (let column = 0; column < 8; column += 1) {
        const candidate = { x: 120 + column * (width + gap), y: 120 + row * (height + gap) };
        const overlaps = canvas.nodes.some((node) => candidate.x < node.x + (node.width || width) + gap && candidate.x + width + gap > node.x && candidate.y < node.y + (node.height || height) + gap && candidate.y + height + gap > node.y);
        if (!overlaps) return candidate;
      }
    }
    return { x: 120 + (canvas.nodes.length % 4) * 320, y: 120 + Math.floor(canvas.nodes.length / 4) * 260 };
  };

  const focusNode = (node, nextZoom = zoom) => {
    const surface = surfaceRef.current;
    if (!surface || !node) return;
    const width = surface.clientWidth;
    const height = surface.clientHeight;
    setPan({
      x: width / 2 - (node.x + (node.width || 280) / 2) * nextZoom,
      y: height / 2 - (node.y + (node.height || 180) / 2) * nextZoom,
    });
  };

  const scenePoint = (event) => {
    const surface = surfaceRef.current;
    if (!surface) return { x: 0, y: 0 };
    const rect = surface.getBoundingClientRect();
    return { x: (event.clientX - rect.left - pan.x) / zoom, y: (event.clientY - rect.top - pan.y) / zoom };
  };

  const fitCanvas = () => {
    const surface = surfaceRef.current;
    if (!surface || !canvas.nodes.length) {
      setPan({ x: 32, y: 28 });
      setZoom(0.82);
      return;
    }
    const padding = 72;
    const minX = Math.min(...canvas.nodes.map((node) => node.x));
    const minY = Math.min(...canvas.nodes.map((node) => node.y));
    const maxX = Math.max(...canvas.nodes.map((node) => node.x + (node.width || 280)));
    const maxY = Math.max(...canvas.nodes.map((node) => node.y + (node.height || 180)));
    const nextZoom = Math.min(1.15, Math.max(0.35, Math.min((surface.clientWidth - padding * 2) / (maxX - minX), (surface.clientHeight - padding * 2) / (maxY - minY))));
    setZoom(Number(nextZoom.toFixed(2)));
    setPan({
      x: surface.clientWidth / 2 - ((minX + maxX) / 2) * nextZoom,
      y: surface.clientHeight / 2 - ((minY + maxY) / 2) * nextZoom,
    });
  };

  const addNode = async (type) => {
    const draft = seedNode(type);
    const position = findOpenPosition();
    draft.x = position.x;
    draft.y = position.y;
    try {
      const node = await actions.createCanvasNode(draft);
      setCanvas((current) => ({ ...current, nodes: [...current.nodes, node] }));
      setSelectedId(node.id);
      setPaletteOpen(false);
      window.setTimeout(() => focusNode(node), 0);
    } catch (error) { actions.notify?.(error?.message || "节点创建失败", "error"); }
  };

  const handlePointerDown = (event, node) => {
    if (connectionMode) {
      if (connectingId) finishConnect(node.id);
      else startConnect(node.id);
      return;
    }
    setSelectedEdgeId(null);
    surfaceRef.current?.setPointerCapture?.(event.pointerId);
    setDrag({ id: node.id, startX: event.clientX, startY: event.clientY, originX: node.x, originY: node.y });
  };
  const handlePointerMove = (event) => {
    if (connectionDrag) {
      const point = scenePoint(event);
      setConnectionDrag((current) => current ? { ...current, x: point.x, y: point.y } : current);
      return;
    }
    if (viewportDrag) {
      setPan({ x: viewportDrag.originX + event.clientX - viewportDrag.startX, y: viewportDrag.originY + event.clientY - viewportDrag.startY });
      return;
    }
    if (!drag) return;
    const dx = (event.clientX - drag.startX) / zoom;
    const dy = (event.clientY - drag.startY) / zoom;
    setCanvas((current) => ({ ...current, nodes: current.nodes.map((item) => item.id === drag.id ? { ...item, x: Math.max(20, drag.originX + dx), y: Math.max(20, drag.originY + dy) } : item) }));
  };
  const handlePointerUp = async (event) => {
    if (connectionDrag) {
      setConnectionDrag(null);
      actions.notify?.("连接已取消");
      return;
    }
    if (viewportDrag) {
      setViewportDrag(null);
      event?.currentTarget?.releasePointerCapture?.(event.pointerId);
      return;
    }
    if (!drag) return;
    const moved = canvas.nodes.find((node) => node.id === drag.id);
    setDrag(null);
    event?.currentTarget?.releasePointerCapture?.(event.pointerId);
    if (moved) await actions.patchCanvasNode(moved.id, { x: moved.x, y: moved.y }).catch(() => {});
  };
  const createConnection = async (sourceId, targetId) => {
    if (!sourceId) return false;
    if (sourceId === targetId) {
      actions.notify?.("不能把节点连接到自身", "error");
      return false;
    }
    if (canvas.edges.some((edge) => edge.source === sourceId && edge.target === targetId)) {
      actions.notify?.("这两个节点已经连接", "error");
      return false;
    }
    const source = nodeMap.get(sourceId);
    const target = nodeMap.get(targetId);
    try {
      const edge = await actions.createCanvasEdge({ source: sourceId, target: targetId, label: `${source?.title || sourceId} → ${target?.title || targetId}` });
      setCanvas((current) => ({ ...current, edges: [...current.edges, edge] }));
      setSelectedId(targetId);
      setSelectedEdgeId(null);
      actions.notify?.("节点连接已创建");
      return true;
    } catch (error) {
      actions.notify?.(error?.message || "节点连接失败", "error");
      return false;
    }
  };
  const cancelConnection = (message = "已退出连接模式") => {
    setConnectionMode(false);
    setConnectingId(null);
    setConnectionDrag(null);
    if (message) actions.notify?.(message);
  };
  const startConnectDrag = (event, nodeId) => {
    const source = nodeMap.get(nodeId);
    if (!source) return;
    const point = scenePoint(event);
    setConnectionMode(false);
    setPanMode(false);
    setConnectingId(null);
    setSelectedId(nodeId);
    setSelectedEdgeId(null);
    setConnectionDrag({ sourceId: nodeId, pointerId: event.pointerId, x: point.x, y: point.y });
    actions.notify?.("连接带已拉出，请拖到目标节点或输入端口");
  };
  const finishConnectDrag = async (event, targetId) => {
    event?.stopPropagation?.();
    if (!connectionDrag) return;
    const sourceId = connectionDrag.sourceId;
    setConnectionDrag(null);
    const created = await createConnection(sourceId, targetId);
    if (!created) actions.notify?.("连接未创建，请拖到另一个节点的输入端口", "error");
  };
  useEffect(() => {
    if (!connectionMode && !connectingId && !connectionDrag) return undefined;
    const onKeyDown = (event) => {
      if (event.key === "Escape") cancelConnection();
    };
    const onContextMenu = (event) => {
      event.preventDefault();
      cancelConnection();
    };
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("contextmenu", onContextMenu);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("contextmenu", onContextMenu);
    };
  }, [connectionMode, connectingId, connectionDrag]);
  const handleScenePointerDown = (event) => {
    if (event.target !== event.currentTarget) return;
    setSelectedId(null);
    setSelectedEdgeId(null);
    if (connectionMode) {
      cancelConnection();
      return;
    }
    if (!panMode) return;
    surfaceRef.current?.setPointerCapture?.(event.pointerId);
    setViewportDrag({ startX: event.clientX, startY: event.clientY, originX: pan.x, originY: pan.y });
  };
  const startConnect = (nodeId) => { setConnectionMode(true); setPanMode(false); setConnectingId(nodeId); setSelectedId(nodeId); setSelectedEdgeId(null); actions.notify?.("已选择起点，请点击目标节点或它左侧的输入端口"); };
  const finishConnect = async (targetId) => {
    if (!connectingId) { actions.notify?.("请先选择一个起点"); return; }
    const sourceId = connectingId;
    setConnectingId(null);
    setConnectionMode(false);
    await createConnection(sourceId, targetId);
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
      cancelConnection();
    } else {
      setPanMode(false);
      setConnectionMode(true);
      setSelectedEdgeId(null);
      actions.notify?.("连接模式：点击一个节点作为起点，再点击目标节点");
    }
  };
  const handleWheel = (event) => {
    if (!event.ctrlKey) return;
    event.preventDefault();
    const surface = surfaceRef.current;
    if (!surface) return;
    const rect = surface.getBoundingClientRect();
    const anchorX = (event.clientX - rect.left - pan.x) / zoom;
    const anchorY = (event.clientY - rect.top - pan.y) / zoom;
    const nextZoom = Math.min(1.35, Math.max(0.35, zoom * Math.exp(-event.deltaY * 0.0025)));
    setZoom(Number(nextZoom.toFixed(3)));
    setPan({ x: event.clientX - rect.left - anchorX * nextZoom, y: event.clientY - rect.top - anchorY * nextZoom });
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
  const previewPath = (connection, source) => {
    if (!source) return "";
    const sx = source.x + (source.width || 280);
    const sy = source.y + (source.height || 180) / 2;
    const tx = connection.x;
    const ty = connection.y;
    const bend = Math.max(90, Math.abs(tx - sx) * 0.48);
    return `M ${sx} ${sy} C ${sx + bend} ${sy}, ${tx - bend} ${ty}, ${tx} ${ty}`;
  };

  const updateSelectedNode = (node) => {
    if (!node) {
      setSelectedId(null);
      setSelectedEdgeId(null);
      return;
    }
    setSelectedId(node.id);
    setSelectedEdgeId(null);
    setCanvas((current) => ({ ...current, nodes: current.nodes.map((item) => item.id === node.id ? node : item) }));
  };

  return <div className="canvas-page">
    <header className="canvas-toolbar"><div className="canvas-toolbar-title"><span>INFINITE CANVAS</span><h1>生产画布</h1><p>把故事、资产、镜头和生成任务连成一条可执行工作流</p></div><div className="canvas-toolbar-actions"><button type="button" className={connectionMode ? "is-active" : ""} onClick={toggleConnectionMode}><LinkSimple size={16} />{connectionMode ? "退出连接" : "连接节点"}</button><div className="canvas-add-wrap"><button className="primary-action" type="button" onClick={() => setPaletteOpen((open) => !open)}><Plus size={17} />添加节点</button>{paletteOpen && <div className="canvas-node-palette">{NODE_TYPES.map((item) => <button type="button" key={item.type} onClick={() => addNode(item.type)}><i className={`palette-dot tone-${item.tone}`} /><span><strong>{item.label}</strong><small>{item.hint}</small></span></button>)}</div>}</div></div></header>
    <div className="canvas-workspace">
      <aside className="canvas-left-rail"><div className="canvas-rail-heading"><span>WORKFLOW</span><strong>{canvas.nodes.length} 节点</strong></div><div className="canvas-mini-map"><div className="mini-map-grid">{canvas.nodes.map((node) => <button type="button" key={node.id} className={`mini-map-node tone-${nodeType(node.type).tone} ${selectedId === node.id ? "is-selected" : ""}`} style={{ left: `${Math.min(88, Math.max(4, node.x / 16))}%`, top: `${Math.min(86, Math.max(4, node.y / 8))}%` }} onClick={() => { setSelectedId(node.id); setSelectedEdgeId(null); focusNode(node); }} aria-label={`定位到${node.title}`} title={`定位到${node.title}`} />)}</div></div><div className="canvas-rail-section"><span>当前项目</span><strong>{project.title}</strong><small>{project.currentEpisodeId} · {project.episodes.find((item) => item.id === project.currentEpisodeId)?.title}</small></div><div className="canvas-rail-section"><span>工作流建议</span><p><b>1</b>故事 → Agent → 脚本</p><p><b>2</b>参考资产 → 镜头 → 视频</p><p><b>3</b>视频与音频 → 时间线</p></div><button className="canvas-rail-help" type="button" onClick={() => actions.notify?.("开启连接模式后，点击节点或输入端口建立上下游连接")}>使用提示 <ArrowRight size={14} /></button></aside>
      <section className={`canvas-surface ${connectionMode || connectionDrag ? "is-linking" : ""} ${panMode ? "is-pan-mode" : ""}`} ref={surfaceRef} onWheel={handleWheel} onPointerMove={handlePointerMove} onPointerUp={handlePointerUp} onPointerCancel={handlePointerUp}>
        <div className="canvas-surface-tools"><button type="button" aria-label="放大画布" title="放大画布" onClick={() => setZoom((value) => Math.min(1.35, Number((value + 0.1).toFixed(2))))}><Plus size={15} /></button><span aria-live="polite">{Math.round(zoom * 100)}%</span><button type="button" aria-label="缩小画布" title="缩小画布" onClick={() => setZoom((value) => Math.max(0.35, Number((value - 0.1).toFixed(2))))}><Minus size={15} /></button><i /><button type="button" aria-label="适配全部节点" title="适配全部节点" onClick={fitCanvas}><ArrowsOut size={15} /></button><button type="button" className={`hand-tool ${panMode ? "is-active" : ""}`} aria-label={panMode ? "退出平移模式" : "平移画布"} aria-pressed={panMode} title={panMode ? "退出平移模式" : "平移画布"} onClick={() => { setPanMode((value) => !value); setConnectionMode(false); setConnectingId(null); }}><Hand size={15} /></button></div>
        <div className="canvas-scene" style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})` }} onPointerDown={handleScenePointerDown}><svg className="canvas-edges" width="1800" height="1200"><defs><linearGradient id="canvas-edge-gradient" x1="0" x2="1"><stop offset="0" stopColor="#8cb7ff" /><stop offset="1" stopColor="#5a80f6" /></linearGradient><marker id="canvas-edge-arrow" markerWidth="9" markerHeight="9" refX="7" refY="4" orient="auto" markerUnits="strokeWidth"><path d="M 0 0 L 8 4 L 0 8 z" fill="#5a80f6" /></marker></defs>{canvas.edges.map((edge) => { const source = nodeMap.get(edge.source); const target = nodeMap.get(edge.target); return <path key={edge.id} d={pathFor(edge)} className={`canvas-edge-path ${selectedEdgeId === edge.id ? "is-selected" : ""}`} markerEnd="url(#canvas-edge-arrow)" role="button" tabIndex="0" aria-label={`${source?.title || edge.source}连接到${target?.title || edge.target}`} onPointerDown={(event) => { event.stopPropagation(); setSelectedId(null); setSelectedEdgeId(edge.id); }} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setSelectedId(null); setSelectedEdgeId(edge.id); } }} />; })}{connectionDrag && <path d={previewPath(connectionDrag, nodeMap.get(connectionDrag.sourceId))} className="canvas-edge-preview" markerEnd="url(#canvas-edge-arrow)" />}</svg>{canvas.nodes.map((node) => <CanvasNode key={node.id} node={node} selected={selectedId === node.id} connecting={connectingId === node.id || connectionDrag?.sourceId === node.id} connectionDrag={connectionDrag} linkMode={connectionMode} linkTarget={(connectionMode && Boolean(connectingId) && connectingId !== node.id) || (connectionDrag && connectionDrag.sourceId !== node.id)} onSelect={(nodeId) => { setSelectedId(nodeId); setSelectedEdgeId(null); }} onDragStart={handlePointerDown} onConnectStart={startConnect} onConnectTarget={finishConnect} onConnectDragStart={startConnectDrag} onConnectDragEnd={finishConnectDrag} onRun={runNode} onDelete={deleteNode} />)}</div>
        {connectionMode && <div className="canvas-linking-hint"><LinkSimple size={15} />{connectingId ? `正在从「${canvas.nodes.find((node) => node.id === connectingId)?.title}」连接到目标节点` : "连接模式：点击一个节点作为起点"}</div>}
        {!canvas.nodes.length && <div className="canvas-empty"><Sparkle size={28} /><strong>开始搭建你的生产画布</strong><p>添加文本、Agent、图片和视频节点，连线后就能沿着工作流执行。</p><button className="primary-action" type="button" onClick={() => addNode("text")}><Plus size={16} />添加第一个节点</button></div>}
      </section>
      <CanvasInspector node={selectedNode} edge={selectedEdge} edges={canvas.edges} nodes={canvas.nodes} episodes={project.episodes || []} onChange={updateSelectedNode} onCloseEdge={() => setSelectedEdgeId(null)} onSave={saveNode} onRun={runNode} onDelete={deleteNode} onDeleteEdge={deleteEdge} />
    </div>
  </div>;
}
