import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowClockwise, BracketsCurly, CheckCircle, CloudArrowUp, FileArrowUp, FloppyDisk, GearSix, Lightning, Play, Trash, UploadSimple, WarningCircle } from "@phosphor-icons/react";

function unwrapWorkflow(value) {
  if (value?.prompt && typeof value.prompt === "string") {
    try { return JSON.parse(value.prompt); } catch { return value; }
  }
  return value;
}

function workflowNodes(apiJson) {
  return Object.entries(unwrapWorkflow(apiJson) || {}).filter(([, node]) => node && typeof node === "object" && node.inputs).map(([nodeId, node]) => ({
    nodeId,
    title: node._meta?.title || node.class_type || `节点 ${nodeId}`,
    classType: node.class_type || "未知节点",
    inputs: Object.entries(node.inputs || {}),
  }));
}

function isReference(value) {
  return Array.isArray(value) && value.length === 2 && typeof value[0] === "string" && Number.isInteger(value[1]);
}

function isMediaField(fieldName) {
  return /image|audio|video|file|upload/i.test(fieldName);
}

function nodeInfoList(apiJson) {
  return workflowNodes(apiJson).flatMap((node) => node.inputs.filter(([fieldName, value]) => !isReference(value) && (typeof value === "string" || typeof value === "number" || typeof value === "boolean")).map(([fieldName, fieldValue]) => ({ nodeId: node.nodeId, fieldName, fieldValue })));
}

function updateWorkflowValue(apiJson, nodeId, fieldName, value) {
  const next = JSON.parse(JSON.stringify(apiJson || {}));
  if (next[nodeId]?.inputs) next[nodeId].inputs[fieldName] = value;
  return next;
}

function prettyStatus(status) {
  return { Queued: "排队中", Running: "运行中", Processing: "处理中", Success: "成功", Failed: "失败", Cancelled: "已取消" }[status] || status || "等待";
}

function WorkflowList({ workflows, selectedId, onSelect, onImport }) {
  const inputRef = useRef(null);
  const handleImport = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (file) await onImport(file);
  };
  return <aside className="rh-workflow-list"><div className="rh-list-heading"><div><span>WORKSPACE</span><strong>我的工作流</strong></div><button type="button" title="导入工作流 JSON" onClick={() => inputRef.current?.click()}><FileArrowUp size={17} /></button><input ref={inputRef} type="file" accept=".json,application/json" hidden onChange={handleImport} /></div><label className="rh-search"><span>⌕</span><input placeholder="搜索工作流" /></label><div className="rh-list-items">{workflows.map((workflow) => <button type="button" className={`rh-workflow-item ${selectedId === workflow.id ? "is-active" : ""}`} key={workflow.id} onClick={() => onSelect(workflow.id)}><span className="rh-workflow-icon"><BracketsCurly size={17} /></span><span><strong>{workflow.name}</strong><small>{workflow.workflowId || "未绑定 Workflow ID"}</small></span><i className={`rh-dot ${workflow.status}`} /></button>)}{!workflows.length && <div className="rh-list-empty"><CloudArrowUp size={25} /><strong>还没有工作流</strong><span>导入 RunningHub 导出的 API JSON 开始。</span><button type="button" onClick={() => inputRef.current?.click()}>导入 JSON</button></div>}</div><div className="rh-list-foot"><span>RunningHub API</span><small>工作流配置保存在本机项目库</small></div></aside>;
}

function NodeField({ nodeId, fieldName, value, onChange, onUpload }) {
  const inputRef = useRef(null);
  const reference = isReference(value);
  const media = isMediaField(fieldName) && !reference;
  const largeText = typeof value === "string" && (value.length > 70 || /prompt|text|description|negative/i.test(fieldName));
  const upload = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (file) await onUpload(nodeId, fieldName, file);
  };
  return <div className={`rh-field ${reference ? "is-reference" : ""}`}><div className="rh-field-label"><span>{fieldName}</span>{media && <><button type="button" onClick={() => inputRef.current?.click()}><UploadSimple size={13} />上传</button><input ref={inputRef} type="file" hidden accept="image/*,audio/*,video/*,.zip" onChange={upload} /></>}</div>{reference ? <code>[{value.join(", ")}] · 节点引用</code> : typeof value === "boolean" ? <label className="rh-toggle"><input type="checkbox" checked={value} onChange={(event) => onChange(event.target.checked)} /><span>{value ? "true" : "false"}</span></label> : largeText ? <textarea value={String(value ?? "")} onChange={(event) => onChange(event.target.value)} /> : <input value={String(value ?? "")} type={typeof value === "number" ? "number" : "text"} onChange={(event) => onChange(typeof value === "number" ? Number(event.target.value) : event.target.value)} />}</div>;
}

function WorkflowEditor({ workflow, onChange, onSave, onUpload, saving }) {
  const nodes = useMemo(() => workflowNodes(workflow?.apiJson), [workflow?.apiJson]);
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  useEffect(() => { if (!nodes.some((node) => node.nodeId === selectedNodeId)) setSelectedNodeId(nodes[0]?.nodeId || null); }, [nodes, selectedNodeId]);
  const selectedNode = nodes.find((node) => node.nodeId === selectedNodeId) || nodes[0];
  return <section className="rh-editor"><div className="rh-editor-head"><div><span className="section-kicker">WORKFLOW EDITOR</span><input className="rh-title-input" value={workflow.name} onChange={(event) => onChange({ ...workflow, name: event.target.value })} /><p>{nodes.length} 个节点 · 修改后提交时映射为 nodeInfoList</p></div><button className="primary-action" type="button" onClick={() => onSave(workflow)} disabled={saving}><FloppyDisk size={16} />{saving ? "保存中…" : "保存工作流"}</button></div><div className="rh-editor-meta"><label>Workflow ID<input value={workflow.workflowId} onChange={(event) => onChange({ ...workflow, workflowId: event.target.value })} placeholder="从 RunningHub 工作流 URL 获取" /></label><label>说明<input value={workflow.description || ""} onChange={(event) => onChange({ ...workflow, description: event.target.value })} placeholder="这个工作流用于什么生成任务？" /></label></div>{nodes.length ? <div className="rh-node-editor"><div className="rh-node-rail">{nodes.map((node) => <button type="button" className={selectedNode?.nodeId === node.nodeId ? "is-active" : ""} key={node.nodeId} onClick={() => setSelectedNodeId(node.nodeId)}><b>{node.nodeId}</b><span><strong>{node.title}</strong><small>{node.classType}</small></span><i>{node.inputs.length}</i></button>)}</div><div className="rh-node-fields">{selectedNode ? <><div className="rh-node-fields-head"><div><span>NODE {selectedNode.nodeId}</span><h3>{selectedNode.title}</h3></div><code>{selectedNode.classType}</code></div>{selectedNode.inputs.map(([fieldName, value]) => <NodeField key={fieldName} nodeId={selectedNode.nodeId} fieldName={fieldName} value={value} onChange={(nextValue) => onChange({ ...workflow, apiJson: updateWorkflowValue(workflow.apiJson, selectedNode.nodeId, fieldName, nextValue) })} onUpload={onUpload} />)}</> : <div className="rh-empty-state">选择一个节点编辑参数</div>}</div></div> : <div className="rh-empty-state"><BracketsCurly size={28} /><strong>工作流 JSON 为空</strong><span>请重新导入 RunningHub 导出的 API JSON。</span></div>}</section>;
}

function RunPanel({ workflow, tasks, providerConfigured, onRun, onDelete, running }) {
  const fields = nodeInfoList(workflow?.apiJson);
  return <aside className="rh-run-panel"><div className="rh-run-card"><div className="rh-run-card-head"><div><span className="section-kicker">RUN CONTROL</span><h2>运行工作流</h2></div><Lightning size={21} weight="duotone" /></div><div className={`rh-connection-state ${providerConfigured ? "is-ready" : "is-missing"}`}>{providerConfigured ? <CheckCircle size={15} /> : <WarningCircle size={15} />}{providerConfigured ? "RunningHub API 已配置" : "需要配置 RunningHub API Key"}</div><div className="rh-run-summary"><div><span>可提交参数</span><strong>{fields.length}</strong></div><div><span>工作流 ID</span><strong>{workflow?.workflowId || "未填写"}</strong></div></div><p>提交时会把当前节点中的文本、数值、布尔值和已上传文件转换成 `nodeInfoList`。</p><button className="primary-action rh-run-button" type="button" onClick={() => onRun(workflow, fields)} disabled={running || !providerConfigured || !workflow?.workflowId}>{running ? "正在提交…" : <><Play size={16} weight="fill" />运行工作流</>}</button></div><div className="rh-result-card"><div className="rh-run-card-head"><div><span className="section-kicker">TASKS & OUTPUTS</span><h2>最近任务</h2></div><ArrowClockwise size={16} /></div>{tasks.length ? <div className="rh-task-list">{tasks.slice(0, 6).map((task) => <div className="rh-task-row" key={task.id}><div><strong>{task.id}</strong><small>{prettyStatus(task.status)} · {task.provider || "RunningHub"}</small></div><em className={`task-status ${task.status}`}>{task.progress || 0}%</em></div>)}</div> : <small className="rh-muted">运行结果会显示在这里，并同步进入统一任务中心。</small>}</div><button className="rh-delete-workflow" type="button" onClick={() => onDelete(workflow)}><Trash size={14} />删除当前工作流</button></aside>;
}

function RunningHubSettings({ actions }) {
  const [settings, setSettings] = useState({ runninghubBaseUrl: "https://www.runninghub.cn", runninghubApiKey: "", runninghubApiKeySet: false });
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { actions.getProviderSettings().then((next) => setSettings((current) => ({ ...current, ...next }))).catch(() => setNotice("配置读取失败")); }, []);
  const update = (key, value) => setSettings((current) => ({ ...current, [key]: value }));
  const save = async () => { setBusy(true); try { const next = await actions.saveProviderSettings(settings); setSettings((current) => ({ ...current, ...next })); setNotice("RunningHub 配置已保存"); } catch (error) { setNotice(error?.message || "保存失败"); } finally { setBusy(false); } };
  const test = async () => { setBusy(true); try { const result = await actions.testProviderSettings({ kind: "runninghub", ...settings }); setNotice(result.message || "连接测试完成"); } catch (error) { setNotice(error?.message || "连接失败"); } finally { setBusy(false); } };
  return <section className="rh-api-settings"><div><span className="section-kicker">API CONNECTION</span><h2>连接 RunningHub</h2><p>API Key 只写入本机加密设置，页面不会回显明文。</p></div><label>API 地址<input value={settings.runninghubBaseUrl || ""} onChange={(event) => update("runninghubBaseUrl", event.target.value)} /></label><label>API Key<input type="password" value={settings.runninghubApiKey || ""} onChange={(event) => update("runninghubApiKey", event.target.value)} placeholder={settings.runninghubApiKeySet ? "已保存，留空保持不变" : "粘贴 RunningHub API Key"} autoComplete="off" /></label><div className="rh-api-actions"><button type="button" onClick={test} disabled={busy}>测试连接</button><button className="primary-action" type="button" onClick={save} disabled={busy}>{busy ? "处理中…" : "保存配置"}</button></div>{notice && <small className="rh-settings-notice">{notice}</small>}</section>;
}

export function RunningHubPage({ project, actions }) {
  const [workflows, setWorkflows] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [activeTab, setActiveTab] = useState("workflow");
  const [draft, setDraft] = useState(null);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  const [notice, setNotice] = useState("");
  const providerConfigured = Boolean(actions.providerInfo?.providers?.workflow?.configured);
  const tasks = useMemo(() => project.tasks.filter((task) => task.targetType === "runninghub_workflow" || task.type === "工作流"), [project.tasks]);
  useEffect(() => { if (actions.backendStatus !== "online") return; actions.getRunningHubWorkflows().then((items) => { setWorkflows(items); if (items[0]) { setSelectedId(items[0].id); setDraft(items[0]); } }).catch((error) => setNotice(error?.message || "工作流读取失败")); }, [actions.backendStatus]);
  useEffect(() => { const next = workflows.find((item) => item.id === selectedId); if (next) setDraft(next); }, [selectedId]);
  const importWorkflow = async (file) => { try { const apiJson = JSON.parse(await file.text()); const workflow = await actions.createRunningHubWorkflow({ name: file.name.replace(/\.json$/i, ""), apiJson }); setWorkflows((current) => [workflow, ...current]); setSelectedId(workflow.id); setDraft(workflow); setActiveTab("workflow"); setNotice("工作流 JSON 已导入，请填写 Workflow ID 后保存"); } catch (error) { setNotice(error?.message || "工作流 JSON 导入失败"); } };
  const saveWorkflow = async (workflow) => { setSaving(true); try { const next = await actions.patchRunningHubWorkflow(workflow.id, { name: workflow.name, workflowId: workflow.workflowId, description: workflow.description, apiJson: workflow.apiJson }); setWorkflows((current) => current.map((item) => item.id === next.id ? next : item)); setDraft(next); setNotice("工作流已保存"); } catch (error) { setNotice(error?.message || "工作流保存失败"); } finally { setSaving(false); } };
  const runWorkflow = async (workflow, fields) => { setRunning(true); try { const result = await actions.runRunningHubWorkflow(workflow.id, { nodeInfoList: fields, prompt: workflow.name }); setNotice(`任务已提交：${result.task?.id || "等待返回"}`); } catch (error) { setNotice(error?.message || "工作流提交失败"); } finally { setRunning(false); } };
  const deleteWorkflow = async (workflow) => { if (!workflow) return; try { await actions.deleteRunningHubWorkflow(workflow.id); const next = workflows.filter((item) => item.id !== workflow.id); setWorkflows(next); setSelectedId(next[0]?.id || null); setDraft(next[0] || null); setNotice("工作流已删除"); } catch (error) { setNotice(error?.message || "工作流删除失败"); } };
  const uploadFile = async (nodeId, fieldName, file) => { try { const result = await actions.uploadRunningHubFile(file); const fileName = result.data?.fileName || result.data?.filename; if (!fileName) throw new Error("RunningHub 未返回 fileName"); setDraft((current) => ({ ...current, apiJson: updateWorkflowValue(current.apiJson, nodeId, fieldName, fileName) })); setNotice(`${file.name} 已上传，保存工作流后生效`); } catch (error) { setNotice(error?.message || "文件上传失败"); } };
  return <div className="module-page runninghub-page"><header className="rh-page-header"><div><span className="section-kicker">RUNNINGHUB WORKSPACE</span><h1>云工作流中心</h1><p>导入 ComfyUI API JSON，编辑节点参数，上传输入文件并提交到 RunningHub。</p></div><div className="rh-page-header-actions"><span className={`status-pill ${providerConfigured ? "success" : "muted"}`}>{providerConfigured ? "已连接 RunningHub" : "未配置 API"}</span><button type="button" onClick={() => setActiveTab("api")}><GearSix size={16} />API 设置</button></div></header><nav className="rh-tabs" aria-label="RunningHub 工作区"><button className={activeTab === "workflow" ? "is-active" : ""} type="button" onClick={() => setActiveTab("workflow")}><BracketsCurly size={15} />工作流</button><button className={activeTab === "tasks" ? "is-active" : ""} type="button" onClick={() => setActiveTab("tasks")}><Lightning size={15} />任务与结果 <span>{tasks.length}</span></button><button className={activeTab === "api" ? "is-active" : ""} type="button" onClick={() => setActiveTab("api")}><GearSix size={15} />API 设置</button></nav>{notice && <div className="rh-notice">{notice}</div>}{activeTab === "api" ? <RunningHubSettings actions={actions} /> : activeTab === "tasks" ? <section className="rh-all-tasks"><div className="rh-task-overview"><span className="section-kicker">TASKS & BILLING</span><h2>任务与结果</h2><p>RunningHub 任务与本地图片、视频、音频、Agent 任务统一追踪。</p></div>{tasks.length ? tasks.map((task) => <div className="rh-task-large" key={task.id}><div><strong>{task.id}</strong><span>{task.model} · {task.provider}</span></div><em className={`task-status ${task.status}`}>{prettyStatus(task.status)} · {task.progress || 0}%</em><small>{task.error || "结果会在任务完成后写入任务详情"}</small></div>) : <div className="rh-empty-state"><Lightning size={28} /><strong>还没有 RunningHub 任务</strong><span>从工作流编辑器提交一次任务后，会在这里持续追踪。</span></div>}</section> : <div className="rh-workspace"><WorkflowList workflows={workflows} selectedId={selectedId} onSelect={setSelectedId} onImport={importWorkflow} />{draft ? <WorkflowEditor workflow={draft} onChange={setDraft} onSave={saveWorkflow} onUpload={uploadFile} saving={saving} /> : <section className="rh-empty-state rh-main-empty"><CloudArrowUp size={33} /><strong>把 RunningHub 工作流带进短剧生产</strong><span>导入你的 API JSON 后，就可以在这里改节点参数和运行任务。</span></section>}{draft && <RunPanel workflow={draft} tasks={tasks} providerConfigured={providerConfigured} onRun={runWorkflow} onDelete={deleteWorkflow} running={running} />}</div>}</div>;
}
