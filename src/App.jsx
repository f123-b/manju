import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CheckCircle, Sparkle } from "@phosphor-icons/react";
import { Sidebar, Topbar } from "./components/Chrome.jsx";
import { StoryboardWorkspace } from "./components/StoryboardWorkspace.jsx";
import { ModulePage, SearchDialog } from "./components/ModulePages.jsx";
import {
  cancelRemoteTask,
  createRemoteAsset,
  createRemoteScene,
  createRemoteShot,
  deleteRemoteShot,
  exportRemoteProject,
  generateRemoteBreakdown,
  generateRemoteMatrix,
  generateRemoteAsset,
  generateRemoteCandidates,
  generateRemoteMasterSheet,
  generateRemoteSceneScript,
  generateRemoteShot,
  getRemoteProviderSettings,
  getRemoteAgentRun,
  getRemoteHealth,
  getRemoteProject,
  getRemoteScenes,
  approveRemoteReference,
  rejectRemoteReference,
  extractRemoteAnchors,
  createRemoteCharacterLook,
  activateRemoteTake,
  createRemoteAudioClip,
  patchRemoteAudioClip,
  deleteRemoteAudioClip,
  createRemoteVoiceProfile,
  directRemotePerformance,
  extractRemoteDialogueLines,
  generateRemoteDialogueLine,
  generateRemoteEpisodeDialogue,
  lockRemoteCharacter,
  lockRemoteVoiceProfile,
  mixdownRemoteEpisode,
  renderRemoteEpisode,
  unlockRemoteCharacter,
  unlockRemoteVoiceProfile,
  patchRemoteDialogueLine,
  patchRemoteVoiceProfile,
  patchRemoteCharacter,
  setRemoteCanonical,
  patchRemoteAsset,
  patchRemoteEpisode,
  patchRemoteProject,
  patchRemoteScene,
  patchRemoteShot,
  patchRemoteStoryBible,
  retryRemoteTask,
  startRemoteAgentRun,
  resumeRemoteAgentRun,
  cancelRemoteAgentRun,
  runRemoteTakeQC,
  runRemoteShotQC,
  runRemoteProjectQC,
  runRemoteContinuityCheck,
  saveRemoteProject,
  saveRemoteProviderSettings,
  testRemoteProviderSettings,
} from "./apiClient.js";
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
  const [activeNav, setActiveNav] = useState("Agent");
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
  }, [project, backendStatus]);

  useEffect(() => () => { timers.current.forEach((timer) => window.clearTimeout(timer)); }, []);

  const stats = useMemo(() => getProjectStats(project), [project]);
  const selectShot = useCallback((shotId) => setSelectedShotId(shotId), []);
  const notify = useCallback((message, type = "done") => {
    setToast({ message, type });
    window.setTimeout(() => setToast(null), 2600);
  }, []);

  const persist = useCallback((operation) => {
    operation.catch(() => setBackendStatus("offline"));
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
    notify,
    navigate: setActiveNav,
    backendStatus,
    providerInfo,
    updateProject: (patch) => {
      setProject((current) => ({ ...current, ...patch }));
      if (backendStatus === "online") persist(patchRemoteProject(patch));
    },
    updateStory: (field, value) => {
      setProject((current) => updateStoryBible(current, field, value));
      if (backendStatus === "online") persist(patchRemoteStoryBible({ [field]: value }));
    },
    loadScenes: (episodeId) => {
      if (backendStatus === "online") return getRemoteScenes(episodeId);
      if (episodeId === project.currentEpisodeId && project.currentScene) return Promise.resolve([{ ...project.currentScene, episodeId, order: project.currentScene.number, script: {} }]);
      return Promise.resolve([]);
    },
    saveEpisode: (episodeId, patch) => {
      setProject((current) => ({ ...current, episodes: current.episodes.map((episode) => episode.id === episodeId ? { ...episode, ...patch, hook: patch.hook ?? episode.hook, openingHook: patch.hook ?? episode.openingHook } : episode) }));
      if (backendStatus === "online") return patchRemoteEpisode(episodeId, patch).then((episode) => {
        setProject((current) => ({ ...current, episodes: current.episodes.map((item) => item.id === episodeId ? { ...item, ...episode } : item) }));
        return episode;
      });
      return Promise.resolve({ ...project.episodes.find((episode) => episode.id === episodeId), ...patch });
    },
    generateMatrix: (episodeId, payload) => {
      if (backendStatus !== "online") return Promise.reject(new Error("FastAPI 未连接"));
      return generateRemoteMatrix(episodeId, payload).then((episode) => {
        setProject((current) => ({ ...current, episodes: current.episodes.map((item) => item.id === episodeId ? { ...item, ...episode } : item) }));
        return episode;
      });
    },
    createScene: (episodeId, payload) => {
      if (backendStatus !== "online") return Promise.reject(new Error("FastAPI 未连接"));
      return createRemoteScene(episodeId, payload);
    },
    generateAsset: (assetType, payload) => {
      if (backendStatus !== "online") return Promise.reject(new Error("FastAPI 未连接"));
      return generateRemoteAsset(assetType, payload).then((response) => {
        const asset = response.asset;
        setProject((current) => ({
          ...current,
          assets: {
            ...current.assets,
            [assetType]: current.assets[assetType].some((item) => item.id === asset.id)
              ? current.assets[assetType].map((item) => item.id === asset.id ? asset : item)
              : [...current.assets[assetType], asset],
          },
        }));
        return response;
      });
    },
    extractCharacterAnchors: (characterId) => {
      if (backendStatus !== "online") return Promise.reject(new Error("FastAPI 未连接"));
      return extractRemoteAnchors(characterId).then(async (response) => {
        setProject(await getRemoteProject());
        notify("Identity Anchors 已提取");
        return response;
      });
    },
    generateCharacterCandidates: (characterId, payload = {}) => {
      if (backendStatus !== "online") return Promise.reject(new Error("FastAPI 未连接"));
      return generateRemoteCandidates(characterId, payload).then((response) => {
        getRemoteProject().then(setProject);
        (response.taskIds || []).forEach((taskId) => pollRemoteGeneration(taskId, characterId));
        notify(`已创建 ${response.count} 张候选人物图`);
        return response;
      });
    },
    generateCharacterMasterSheet: (characterId, payload = {}) => {
      if (backendStatus !== "online") return Promise.reject(new Error("FastAPI 未连接"));
      return generateRemoteMasterSheet(characterId, payload).then((response) => {
        getRemoteProject().then(setProject);
        pollRemoteGeneration(response.taskId, characterId);
        notify("Master Reference Sheet 已进入生成队列");
        return response;
      });
    },
    setCharacterCanonical: (characterId, referenceId) => {
      if (backendStatus !== "online") return Promise.reject(new Error("FastAPI 未连接"));
      return setRemoteCanonical(characterId, referenceId).then((character) => {
        setProject((current) => ({ ...current, assets: { ...current.assets, characters: current.assets.characters.map((item) => item.id === character.id ? character : item) } }));
        notify("已选择 Canonical Reference");
        return character;
      });
    },
    reviewCharacterReference: (referenceId, approved) => {
      if (backendStatus !== "online") return Promise.reject(new Error("FastAPI 未连接"));
      return (approved ? approveRemoteReference(referenceId) : rejectRemoteReference(referenceId)).then(async (response) => {
        setProject(await getRemoteProject());
        notify(approved ? "参考图已审核通过" : "参考图已拒绝");
        return response;
      });
    },
    lockCharacter: (characterId) => {
      if (backendStatus !== "online") return Promise.reject(new Error("FastAPI 未连接"));
      return lockRemoteCharacter(characterId).then(async (character) => {
        setProject(await getRemoteProject());
        notify("Identity 已锁定");
        return character;
      });
    },
    unlockCharacter: (characterId) => {
      if (backendStatus !== "online") return Promise.reject(new Error("FastAPI 未连接"));
      return unlockRemoteCharacter(characterId).then(async (character) => {
        setProject(await getRemoteProject());
        notify("Identity 已解锁");
        return character;
      });
    },
    updateCharacter: (characterId, patch) => {
      if (backendStatus !== "online") return Promise.reject(new Error("FastAPI 未连接"));
      return patchRemoteCharacter(characterId, patch).then(async (character) => {
        setProject(await getRemoteProject());
        return character;
      });
    },
    createCharacterLook: (characterId, payload) => {
      if (backendStatus !== "online") return Promise.reject(new Error("FastAPI 未连接"));
      return createRemoteCharacterLook(characterId, payload).then(async (response) => {
        setProject(await getRemoteProject());
        notify("已添加角色造型");
        return response;
      });
    },
    createVoiceProfile: (characterId, payload) => {
      if (backendStatus !== "online") return Promise.reject(new Error("FastAPI 未连接"));
      return createRemoteVoiceProfile(characterId, payload).then(async (profile) => {
        setProject(await getRemoteProject());
        notify("声音档案已创建");
        return profile;
      });
    },
    patchVoiceProfile: (profileId, patch) => {
      if (backendStatus !== "online") return Promise.reject(new Error("FastAPI 未连接"));
      return patchRemoteVoiceProfile(profileId, patch).then(async (profile) => {
        setProject(await getRemoteProject());
        return profile;
      });
    },
    lockVoiceProfile: (profileId) => {
      if (backendStatus !== "online") return Promise.reject(new Error("FastAPI 未连接"));
      return lockRemoteVoiceProfile(profileId).then(async (profile) => {
        setProject(await getRemoteProject());
        notify("声音身份已锁定");
        return profile;
      });
    },
    unlockVoiceProfile: (profileId) => {
      if (backendStatus !== "online") return Promise.reject(new Error("FastAPI 未连接"));
      return unlockRemoteVoiceProfile(profileId).then(async (profile) => {
        setProject(await getRemoteProject());
        notify("声音身份已解锁");
        return profile;
      });
    },
    extractDialogueLines: (sceneId) => {
      if (backendStatus !== "online") return Promise.reject(new Error("FastAPI 未连接"));
      return extractRemoteDialogueLines(sceneId).then(async (lines) => {
        setProject(await getRemoteProject());
        notify(`已提取 ${lines.length} 条台词`);
        return lines;
      });
    },
    patchDialogueLine: (lineId, patch) => {
      if (backendStatus !== "online") return Promise.reject(new Error("FastAPI 未连接"));
      return patchRemoteDialogueLine(lineId, patch).then(async (line) => {
        setProject(await getRemoteProject());
        return line;
      });
    },
    directPerformance: (lineId, payload = {}) => {
      if (backendStatus !== "online") return Promise.reject(new Error("FastAPI 未连接"));
      return directRemotePerformance(lineId, payload).then(async (performance) => {
        setProject(await getRemoteProject());
        notify("AI Voice Direction 已生成");
        return performance;
      });
    },
    generateDialogue: (lineId, payload = {}) => {
      if (backendStatus !== "online") return Promise.reject(new Error("FastAPI 未连接"));
      return generateRemoteDialogueLine(lineId, payload).then((response) => {
        pollRemoteGeneration(response.taskId, `台词 ${lineId}`);
        notify("音频已进入持久任务队列");
        return response;
      });
    },
    generateEpisodeDialogue: (episodeId, payload = {}) => {
      if (backendStatus !== "online") return Promise.reject(new Error("FastAPI 未连接"));
      return generateRemoteEpisodeDialogue(episodeId, payload).then((response) => {
        (response.tasks || []).forEach((task) => pollRemoteGeneration(task.id, `台词 ${task.targetId || task.id}`));
        notify(`已创建 ${response.count || 0} 个音频任务`);
        return response;
      });
    },
    runTakeQC: (takeId) => {
      if (backendStatus !== "online") return Promise.reject(new Error("FastAPI 未连接"));
      return runRemoteTakeQC(takeId).then(async (result) => {
        setProject(await getRemoteProject());
        notify(`音频 QC ${result.status === "pass" ? "通过" : "需要复核"}`);
        return result;
      });
    },
    activateTake: (takeId) => {
      if (backendStatus !== "online") return Promise.reject(new Error("FastAPI 未连接"));
      return activateRemoteTake(takeId).then(async (take) => {
        setProject(await getRemoteProject());
        notify("已启用该版音频");
        return take;
      });
    },
    createAudioClip: (payload) => {
      if (backendStatus !== "online") return Promise.reject(new Error("FastAPI 未连接"));
      return createRemoteAudioClip(payload).then(async (clip) => {
        setProject(await getRemoteProject());
        return clip;
      });
    },
    patchAudioClip: (clipId, payload) => {
      if (backendStatus !== "online") return Promise.reject(new Error("FastAPI 未连接"));
      return patchRemoteAudioClip(clipId, payload).then(async (clip) => {
        setProject(await getRemoteProject());
        return clip;
      });
    },
    deleteAudioClip: (clipId) => {
      if (backendStatus !== "online") return Promise.reject(new Error("FastAPI 未连接"));
      return deleteRemoteAudioClip(clipId).then(async (result) => {
        setProject(await getRemoteProject());
        notify("时间线片段已删除");
        return result;
      });
    },
    mixdownEpisode: (episodeId) => {
      if (backendStatus !== "online") return Promise.reject(new Error("FastAPI 未连接"));
      return mixdownRemoteEpisode(episodeId).then(async (mixdown) => {
        setProject(await getRemoteProject());
        notify("本集混音已生成");
        return mixdown;
      });
    },
    renderEpisode: (episodeId) => {
      if (backendStatus !== "online") return Promise.reject(new Error("FastAPI 未连接"));
      return renderRemoteEpisode(episodeId).then((render) => {
        if (render.status === "blocked") notify(render.error || "MP4 渲染环境未就绪", "error");
        else if (render.status === "ready") notify("MP4 已渲染完成");
        else notify(`MP4 渲染状态：${render.status}`);
        return render;
      });
    },
    getProviderSettings: () => {
      if (backendStatus !== "online") return Promise.reject(new Error("FastAPI 未连接"));
      return getRemoteProviderSettings();
    },
    saveProviderSettings: (payload) => {
      if (backendStatus !== "online") return Promise.reject(new Error("FastAPI 未连接"));
      return saveRemoteProviderSettings(payload).then((settings) => {
        getRemoteHealth().then(setProviderInfo).catch(() => {});
        notify("API 配置已保存，新的任务会立即使用");
        return settings;
      });
    },
    testProviderSettings: (payload = {}) => {
      if (backendStatus !== "online") return Promise.reject(new Error("FastAPI 未连接"));
      return testRemoteProviderSettings(payload);
    },
    startAgentRun: (payload) => {
      if (backendStatus !== "online") return Promise.reject(new Error("FastAPI 未连接"));
      return startRemoteAgentRun(payload);
    },
    getAgentRun: (runId) => {
      if (backendStatus !== "online") return Promise.reject(new Error("FastAPI 未连接"));
      return getRemoteAgentRun(runId);
    },
    resumeAgentRun: (runId) => {
      if (backendStatus !== "online") return Promise.reject(new Error("FastAPI 未连接"));
      return resumeRemoteAgentRun(runId);
    },
    cancelAgentRun: (runId) => {
      if (backendStatus !== "online") return Promise.reject(new Error("FastAPI 未连接"));
      return cancelRemoteAgentRun(runId);
    },
    runShotQC: (shotId) => {
      if (backendStatus !== "online") return Promise.reject(new Error("FastAPI 未连接"));
      return runRemoteShotQC(shotId).then(async (result) => {
        setProject(await getRemoteProject());
        return result;
      });
    },
    runProjectQC: () => {
      if (backendStatus !== "online") return Promise.reject(new Error("FastAPI 未连接"));
      return runRemoteProjectQC().then(async (result) => {
        setProject(await getRemoteProject());
        return result;
      });
    },
    runContinuityCheck: () => {
      if (backendStatus !== "online") return Promise.reject(new Error("FastAPI 未连接"));
      return runRemoteContinuityCheck().then(async (result) => {
        setProject(await getRemoteProject());
        return result;
      });
    },
    saveScene: (sceneId, patch) => {
      if (backendStatus !== "online") return Promise.reject(new Error("FastAPI 未连接"));
      return patchRemoteScene(sceneId, patch);
    },
    generateSceneScript: (sceneId, payload) => {
      if (backendStatus !== "online") return Promise.reject(new Error("FastAPI 未连接"));
      return generateRemoteSceneScript(sceneId, payload);
    },
    generateBreakdown: (sceneId, payload) => {
      if (backendStatus !== "online") return Promise.reject(new Error("FastAPI 未连接"));
      return generateRemoteBreakdown(sceneId, payload).then(async (response) => {
        const remoteProject = await getRemoteProject();
        setProject(remoteProject);
        return response.items || [];
      });
    },
    addRule: (value) => {
      const next = addStoryRule(project, value);
      setProject(next);
      if (backendStatus === "online" && next !== project) persist(patchRemoteStoryBible({ rules: next.storyBible.rules }));
    },
    removeRule: (index) => {
      const next = removeStoryRule(project, index);
      setProject(next);
      if (backendStatus === "online") persist(patchRemoteStoryBible({ rules: next.storyBible.rules }));
    },
    openEpisode: (episodeId) => {
      const firstShot = project.shots.find((shot) => shot.episodeId === episodeId);
      setProject((current) => ({ ...current, currentEpisodeId: episodeId }));
      setSelectedShotId(firstShot?.id || null);
      if (backendStatus === "online") persist(patchRemoteProject({ currentEpisodeId: episodeId }));
      setActiveNav("分镜");
    },
    addAsset: (type) => {
      const config = {
        characters: { prefix: "C", name: "新角色", meta: "待完善", image: "/assets/shot-hero.png" },
        locations: { prefix: "L", name: "新场景", meta: "待完善", image: "/assets/shot-wide.png" },
        props: { prefix: "P", name: "新道具", meta: "待完善", image: "/assets/shot-woman.png" },
      }[type];
      const item = { id: nextAssetId(project.assets[type], config.prefix), name: config.name, meta: config.meta, description: "点击编辑资产描述。", image: config.image, status: "待确认" };
      setProject((current) => ({ ...current, assets: { ...current.assets, [type]: [...current.assets[type], item] } }));
      if (backendStatus === "online") persist(createRemoteAsset(type, item));
      notify("已创建新资产");
    },
    updateAsset: (type, id, patch) => {
      setProject((current) => ({ ...current, assets: { ...current.assets, [type]: current.assets[type].map((item) => item.id === id ? { ...item, ...patch } : item) } }));
      if (backendStatus === "online") persist(patchRemoteAsset(id, patch));
    },
    cancelTask: (taskId) => {
      const timer = timers.current.get(taskId);
      if (timer) window.clearTimeout(timer);
      timers.current.delete(taskId);
      setProject((current) => cancelProjectTask(current, taskId));
      if (backendStatus === "online") persist(cancelRemoteTask(taskId).then((response) => setProject(response.project)));
      notify("任务已取消");
    },
    retryTask: (taskId) => {
      const source = project.tasks.find((task) => task.id === taskId);
      if (!source) return;
      if (backendStatus === "online") {
        retryRemoteTask(taskId).then((response) => {
          setProject(response.project);
          pollRemoteGeneration(response.task.id, source.shotId);
        }).catch(() => {
          setBackendStatus("offline");
          notify("重试任务失败", "error");
        });
        return;
      }
      const nextTaskId = `T${Date.now()}`;
      setProject((current) => retryProjectTask(current, taskId, nextTaskId, formatTimestamp()));
      setToast({ message: `正在重试 ${source.shotId}…`, type: "loading" });
      scheduleCompletion(nextTaskId, source.shotId);
    },
    reviewShot: (shotId) => {
      const shot = project.shots.find((item) => item.id === shotId);
      const reviewed = !shot?.reviewed;
      setProject((current) => updateShot(current, shotId, { reviewed }));
      if (backendStatus === "online") persist(patchRemoteShot(shotId, { reviewed }));
    },
    regenerateShot: (shotId) => {
      const shot = project.shots.find((item) => item.id === shotId);
      if (shot) generateShot(shotId, shot.prompt);
    },
    exportProject: async () => {
      try {
        const blob = backendStatus === "online" ? await exportRemoteProject() : new Blob([JSON.stringify(project, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = backendStatus === "online" ? `${project.title}-project-package.zip` : `${project.title}-project.json`;
        link.click();
        URL.revokeObjectURL(url);
        notify("项目包已导出");
      } catch {
        notify("导出失败，请稍后重试", "error");
      }
    },
  };

  const addNewShot = () => {
    const result = addShot(project);
    setProject(result.project);
    setSelectedShotId(result.shot.id);
    if (backendStatus === "online") persist(createRemoteShot(result.shot.sceneId, result.shot));
    notify(`已添加 ${result.shot.id}`);
  };

  const duplicateCurrentShot = (shotId) => {
    const result = duplicateShot(project, shotId);
    if (!result.shot) return;
    setProject(result.project);
    setSelectedShotId(result.shot.id);
    if (backendStatus === "online") persist(createRemoteShot(result.shot.sceneId, result.shot));
    notify(`已复制为 ${result.shot.id}`);
  };

  const deleteCurrentShot = (shotId) => {
    const currentIndex = project.shots.findIndex((shot) => shot.id === shotId);
    const nextProject = removeShot(project, shotId);
    if (nextProject === project) return;
    const nextShot = nextProject.shots[Math.min(currentIndex, nextProject.shots.length - 1)];
    setProject(nextProject);
    setSelectedShotId(nextShot?.id || null);
    if (backendStatus === "online") persist(deleteRemoteShot(shotId));
    notify(`${shotId} 已删除`);
  };

  const changeEpisode = (episodeId) => {
    const firstShot = project.shots.find((shot) => shot.episodeId === episodeId);
    setProject((current) => ({ ...current, currentEpisodeId: episodeId }));
    setSelectedShotId(firstShot?.id || null);
    if (backendStatus === "online") persist(patchRemoteProject({ currentEpisodeId: episodeId }));
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
              onUpdateShot={(shotId, patch) => {
                setProject((current) => updateShot(current, shotId, patch));
                if (backendStatus === "online") persist(patchRemoteShot(shotId, patch));
              }}
              onUpdateScene={(patch) => {
                setProject((current) => ({ ...current, currentScene: { ...current.currentScene, ...patch } }));
                if (backendStatus === "online" && project.currentScene?.id) persist(patchRemoteScene(project.currentScene.id, patch));
              }}
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
