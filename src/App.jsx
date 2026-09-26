import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CheckCircle, Sparkle } from "@phosphor-icons/react";
import { Sidebar, Topbar } from "./components/Chrome.jsx";
import { StoryboardWorkspace } from "./components/StoryboardWorkspace.jsx";
import { ModulePage, SearchDialog } from "./components/ModulePages.jsx";
import { generateRemoteShot, getRemoteHealth, getRemoteProject, saveRemoteProject } from "./apiClient.js";
import {
  addShot,
  addStoryRule,
  cancelTask as cancelProjectTask,
  completeGeneration,
  duplicateShot,
  getProjectStats,
  loadProject,
  queueGeneration,
  removeShot,
  removeStoryRule,
  retryTask as retryProjectTask,
  saveProject,
  updateShot,
  updateStoryBible,
} from "./projectStore.js";

function formatTimestamp(date = new Date()) {
  const pad = (value) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function nextAssetId(items, prefix) {
  const next = Math.max(...items.map((item) => Number(item.id.replace(/\D/g, ""))), 0) + 1;
  return `${prefix}${String(next).padStart(3, "0")}`;
}

export function App() {
  const [project, setProject] = useState(() => loadProject());
  const [activeNav, setActiveNav] = useState("概览");
  const [selectedShotId, setSelectedShotId] = useState(() => loadProject().shots.find((shot) => shot.episodeId === loadProject().currentEpisodeId)?.id || null);
  const [searchOpen, setSearchOpen] = useState(false);
  const [toast, setToast] = useState(null);
  const [backendStatus, setBackendStatus] = useState("checking");
  const [providerInfo, setProviderInfo] = useState(null);
  const backendHydrated = useRef(false);
  const timers = useRef(new Map());

  useEffect(() => {
    let active = true;
    getRemoteProject()
      .then((remoteProject) => {
        if (!active) return;
        setProject(remoteProject);
        setSelectedShotId(remoteProject.shots.find((shot) => shot.episodeId === remoteProject.currentEpisodeId)?.id || null);
        backendHydrated.current = true;
        setBackendStatus("online");
      })
      .catch((error) => {
        if (error?.status !== 404) {
          if (active) setBackendStatus("offline");
          return;
        }
        saveRemoteProject(project)
          .then(() => {
            backendHydrated.current = true;
            if (active) setBackendStatus("online");
          })
          .catch(() => {
            if (active) setBackendStatus("offline");
          });
      });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    getRemoteHealth().then(setProviderInfo).catch(() => setProviderInfo(null));
  }, [backendStatus]);

  useEffect(() => {
    saveProject(project);
    if (backendStatus === "online" && backendHydrated.current) {
      saveRemoteProject(project).catch(() => setBackendStatus("offline"));
    }
  }, [project, backendStatus]);

  useEffect(() => () => { timers.current.forEach((timer) => window.clearTimeout(timer)); }, []);

  const stats = useMemo(() => getProjectStats(project), [project]);
  const selectShot = useCallback((shotId) => setSelectedShotId(shotId), []);
  const notify = useCallback((message, type = "done") => {
    setToast({ message, type });
    window.setTimeout(() => setToast(null), 2600);
  }, []);

  const scheduleCompletion = useCallback((taskId, shotId) => {
    const timer = window.setTimeout(() => {
      setProject((current) => completeGeneration(current, taskId, formatTimestamp()));
      timers.current.delete(taskId);
      notify(`${shotId} 已生成新版本`);
    }, 2200);
    timers.current.set(taskId, timer);
  }, [notify]);

  const pollRemoteGeneration = useCallback((taskId, shotId, attempt = 0) => {
    const timer = window.setTimeout(async () => {
      try {
        const remoteProject = await getRemoteProject();
        const task = remoteProject.tasks.find((item) => item.id === taskId);
        setProject(remoteProject);
        if (task?.status === "Success") {
          timers.current.delete(taskId);
          notify(`${shotId} 已生成新版本`);
          return;
        }
        if (["Failed", "Cancelled"].includes(task?.status) || attempt >= 60) {
          timers.current.delete(taskId);
          notify(`${shotId} 生成未完成，请在任务中心处理`, "error");
          return;
        }
        pollRemoteGeneration(taskId, shotId, attempt + 1);
      } catch {
        timers.current.delete(taskId);
        setBackendStatus("offline");
        notify("后台连接中断，已切换本地状态", "error");
      }
    }, 800);
    timers.current.set(taskId, timer);
  }, [notify]);

  const generateShot = useCallback(async (shotId, prompt) => {
    if (backendStatus === "online") {
      try {
        setToast({ message: `正在生成 ${shotId}…`, type: "loading" });
        const response = await generateRemoteShot({ shotId, prompt });
        setProject(response.project);
        pollRemoteGeneration(response.task.id, shotId);
        return;
      } catch {
        setBackendStatus("offline");
        notify("后台连接失败，已切换本地演示生成", "error");
      }
    }
    const taskId = `T${Date.now()}`;
    setProject((current) => queueGeneration(current, shotId, prompt, taskId, formatTimestamp()));
    setToast({ message: `正在生成 ${shotId}…`, type: "loading" });
    scheduleCompletion(taskId, shotId);
  }, [backendStatus, notify, pollRemoteGeneration, scheduleCompletion]);

  const actions = {
    navigate: setActiveNav,
    backendStatus,
    providerInfo,
    updateProject: (patch) => setProject((current) => ({ ...current, ...patch })),
    updateStory: (field, value) => setProject((current) => updateStoryBible(current, field, value)),
    addRule: (value) => setProject((current) => addStoryRule(current, value)),
    removeRule: (index) => setProject((current) => removeStoryRule(current, index)),
    openEpisode: (episodeId) => {
      const firstShot = project.shots.find((shot) => shot.episodeId === episodeId);
      setProject((current) => ({ ...current, currentEpisodeId: episodeId }));
      setSelectedShotId(firstShot?.id || null);
      setActiveNav("分镜");
    },
    addAsset: (type) => {
      const config = {
        characters: { prefix: "C", name: "新角色", meta: "待完善", image: "/assets/shot-hero.png" },
        locations: { prefix: "L", name: "新场景", meta: "待完善", image: "/assets/shot-wide.png" },
        props: { prefix: "P", name: "新道具", meta: "待完善", image: "/assets/shot-woman.png" },
      }[type];
      setProject((current) => {
        const items = current.assets[type];
        const item = { id: nextAssetId(items, config.prefix), name: config.name, meta: config.meta, description: "点击编辑资产描述。", image: config.image, status: "待确认" };
        return { ...current, assets: { ...current.assets, [type]: [...items, item] } };
      });
      notify("已创建新资产");
    },
    updateAsset: (type, id, patch) => setProject((current) => ({ ...current, assets: { ...current.assets, [type]: current.assets[type].map((item) => item.id === id ? { ...item, ...patch } : item) } })),
    cancelTask: (taskId) => {
      const timer = timers.current.get(taskId);
      if (timer) window.clearTimeout(timer);
      timers.current.delete(taskId);
      setProject((current) => cancelProjectTask(current, taskId));
      notify("任务已取消");
    },
    retryTask: (taskId) => {
      const source = project.tasks.find((task) => task.id === taskId);
      if (!source) return;
      if (backendStatus === "online") {
        generateShot(source.shotId, project.shots.find((shot) => shot.id === source.shotId)?.prompt || "");
        return;
      }
      const nextTaskId = `T${Date.now()}`;
      setProject((current) => retryProjectTask(current, taskId, nextTaskId, formatTimestamp()));
      setToast({ message: `正在重试 ${source.shotId}…`, type: "loading" });
      scheduleCompletion(nextTaskId, source.shotId);
    },
    reviewShot: (shotId) => setProject((current) => {
      const shot = current.shots.find((item) => item.id === shotId);
      return updateShot(current, shotId, { reviewed: !shot?.reviewed });
    }),
    regenerateShot: (shotId) => {
      const shot = project.shots.find((item) => item.id === shotId);
      if (shot) generateShot(shotId, shot.prompt);
    },
    exportProject: () => {
      const blob = new Blob([JSON.stringify(project, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${project.title}-project.json`;
      link.click();
      URL.revokeObjectURL(url);
      notify("项目包已导出");
    },
  };

  const addNewShot = () => {
    const result = addShot(project);
    setProject(result.project);
    setSelectedShotId(result.shot.id);
    notify(`已添加 ${result.shot.id}`);
  };

  const duplicateCurrentShot = (shotId) => {
    const result = duplicateShot(project, shotId);
    if (!result.shot) return;
    setProject(result.project);
    setSelectedShotId(result.shot.id);
    notify(`已复制为 ${result.shot.id}`);
  };

  const deleteCurrentShot = (shotId) => {
    const currentIndex = project.shots.findIndex((shot) => shot.id === shotId);
    const nextProject = removeShot(project, shotId);
    if (nextProject === project) return;
    const nextShot = nextProject.shots[Math.min(currentIndex, nextProject.shots.length - 1)];
    setProject(nextProject);
    setSelectedShotId(nextShot?.id || null);
    notify(`${shotId} 已删除`);
  };

  const changeEpisode = (episodeId) => {
    const firstShot = project.shots.find((shot) => shot.episodeId === episodeId);
    setProject((current) => ({ ...current, currentEpisodeId: episodeId }));
    setSelectedShotId(firstShot?.id || null);
  };

  const openSearchResult = (result) => {
    if (result.type === "镜头") {
      const shot = project.shots.find((item) => item.id === result.id);
      if (shot) {
        setProject((current) => ({ ...current, currentEpisodeId: shot.episodeId }));
        setSelectedShotId(shot.id);
      }
    }
    if (result.type === "剧集") {
      setProject((current) => ({ ...current, currentEpisodeId: result.id }));
      setSelectedShotId(project.shots.find((shot) => shot.episodeId === result.id)?.id || null);
    }
    setActiveNav(result.target);
    setSearchOpen(false);
  };

  return (
    <div className="app-shell">
      <Topbar project={project} onSearch={() => setSearchOpen(true)} />
      <div className="app-body">
        <Sidebar activeNav={activeNav} onNavigate={setActiveNav} />
        <main className={`content-shell ${activeNav === "分镜" ? "storyboard-mode" : ""}`}>
          {activeNav === "分镜" ? (
            <StoryboardWorkspace
              project={project}
              selectedShotId={selectedShotId}
              onSelectShot={selectShot}
              onAddShot={addNewShot}
              onDuplicateShot={duplicateCurrentShot}
              onDeleteShot={deleteCurrentShot}
              onUpdateShot={(shotId, patch) => setProject((current) => updateShot(current, shotId, patch))}
              onUpdateScene={(patch) => setProject((current) => ({ ...current, currentScene: { ...current.currentScene, ...patch } }))}
              onGenerate={generateShot}
              onEpisodeChange={changeEpisode}
            />
          ) : <ModulePage activeNav={activeNav} project={project} stats={stats} actions={actions} />}
        </main>
      </div>
      <SearchDialog open={searchOpen} project={project} onClose={() => setSearchOpen(false)} onOpenResult={openSearchResult} />
      {toast && <div className={`generation-toast ${toast.type}`}>{toast.type === "loading" ? <Sparkle size={17} /> : <CheckCircle size={17} weight="fill" />}{toast.message}</div>}
    </div>
  );
}
