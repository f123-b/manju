const asset = (name) => `/assets/${name}`;

const defaultPrompt =
  "夜晚，城市天台，冷色调，电影级光影。林泽（黑发，帅气，眼神复杂）看着苏晴，神情坚定又略带心痛。景深虚化的城市夜景，情绪压抑，cinematic，真实感，8k。";

const episodeTitles = [
  "重生归来", "当众拒绝", "撕下伪装", "新的开始", "暗流涌动", "真相浮现",
  "旧情反噬", "旧情难断", "各自为战", "风向逆转", "终局对峙", "新的我",
];

export const initialProject = {
  schemaVersion: 1,
  id: "P001",
  title: "重生之后我不当舔狗了",
  status: "制作中",
  format: "16:9",
  targetEpisodes: 24,
  currentEpisodeId: "EP08",
  dueDate: "2026-10-30",
  budget: 120,
  spent: 52.36,
  production: {
    totalShots: 328,
    generatedShots: 143,
    qcScore: 91,
  },
  storyBible: {
    logline: "重生后的林泽拒绝继续讨好所有人，并用看见财富潜力的能力重新掌控人生。",
    coreConflict: "林泽必须在复仇、成长与重新相信他人之间做出选择。",
    mainLine: "林泽从被背叛的程序员成长为掌控局面的创业者，并揭开苏晴隐瞒的真实身份。",
    theme: "边界、自尊与真正的重生。",
    ending: "林泽放下过去，与真正尊重他的伙伴建立新事业。",
    world: "现代都市，商业竞争与情感关系交织，整体低饱和、冷暖对比。",
    rules: [
      "林泽在 EP08 前不知道苏晴的真实身份。",
      "周凯在 EP15 前不能死亡。",
      "能力只能看到财富潜力，不能直接看到余额。",
    ],
    style: "电影感、现代都市、低饱和、冷暖对比、轻胶片颗粒；避免赛博朋克与过度霓虹。",
  },
  episodes: Array.from({ length: 24 }, (_, index) => {
    const number = index + 1;
    const id = `EP${String(number).padStart(2, "0")}`;
    return {
      id,
      title: episodeTitles[index] || `第 ${String(number).padStart(2, "0")} 集`,
      status: number <= 7 ? "已完成" : number === 8 ? "分镜中" : number <= 12 ? "已策划" : "待策划",
      hook: number === 8 ? "旧爱在天台拦住林泽，逼他面对过去。" : "一个新的决定改变了故事走向。",
      scenes: number === 8 ? 6 : number <= 7 ? 7 : 0,
      shots: number === 8 ? 24 : number <= 7 ? 18 + (number % 4) : 0,
      duration: number <= 8 ? "01:32" : "--:--",
    };
  }),
  currentScene: {
    id: "SC03",
    number: 3,
    title: "天台上的真相",
    purpose: "林泽拒绝苏晴的挽回，完成与过去的切割。",
  },
  shots: [
    { id: "SH041", episodeId: "EP08", sceneId: "SC03", time: "00:00 – 00:04", description: "林泽看着苏晴，眼神复杂", size: "近景", duration: 4, image: asset("shot-hero.png"), status: "已生成", qcScore: 92, reviewed: false, frame: "16:9（横屏）", lens: "85mm（中长焦，人物特写）", angle: "平视", movement: "微推（Slow Push In）", dialogue: "你真的以为，我还会像以前一样吗？", prompt: defaultPrompt, characterIds: ["C001", "C002"], outfitId: "O001", cost: 0.73, versions: [{ id: "V1", createdAt: "2026-09-26 09:20", active: true }] },
    { id: "SH042", episodeId: "EP08", sceneId: "SC03", time: "00:04 – 00:08", description: "苏晴情绪收敛，质问林泽", size: "中景", duration: 4, image: asset("shot-woman.png"), status: "已生成", qcScore: 89, reviewed: false, frame: "16:9（横屏）", lens: "50mm（标准镜头）", angle: "平视", movement: "固定镜头", dialogue: "所以你一直都在骗我？", prompt: defaultPrompt, characterIds: ["C002"], outfitId: "O002", cost: 0.68, versions: [{ id: "V1", createdAt: "2026-09-26 09:24", active: true }] },
    { id: "SH043", episodeId: "EP08", sceneId: "SC03", time: "00:08 – 00:12", description: "两人对峙，城市夜景", size: "全景", duration: 4, image: asset("shot-wide.png"), status: "已生成", qcScore: 95, reviewed: true, frame: "16:9（横屏）", lens: "35mm（环境人像）", angle: "平视", movement: "缓慢拉远", dialogue: "真相从来都不是你想的那样。", prompt: defaultPrompt, characterIds: ["C001", "C002"], outfitId: "O001", cost: 0.81, versions: [{ id: "V1", createdAt: "2026-09-26 09:30", active: true }] },
    { id: "SH044", episodeId: "EP08", sceneId: "SC03", time: "00:12 – 00:16", description: "林泽冷静回应", size: "近景", duration: 4, image: asset("shot-hero.png"), status: "已生成", qcScore: 93, reviewed: false, frame: "16:9（横屏）", lens: "85mm（中长焦，人物特写）", angle: "平视", movement: "固定镜头", dialogue: "到此为止吧。", prompt: defaultPrompt, characterIds: ["C001"], outfitId: "O001", cost: 0.72, versions: [{ id: "V1", createdAt: "2026-09-26 09:35", active: true }] },
    { id: "SH045", episodeId: "EP08", sceneId: "SC03", time: "00:16 – 00:20", description: "苏晴渐渐心软，转身离开", size: "特写", duration: 4, image: asset("shot-woman.png"), status: "待生成", qcScore: null, reviewed: false, frame: "16:9（横屏）", lens: "85mm（中长焦，人物特写）", angle: "平视", movement: "微推（Slow Push In）", dialogue: "苏晴没有回答。", prompt: defaultPrompt, characterIds: ["C002"], outfitId: "O002", cost: 0, versions: [] },
    { id: "SH046", episodeId: "EP08", sceneId: "SC03", time: "00:20 – 00:24", description: "林泽独自站在天台", size: "远景", duration: 4, image: asset("shot-wide.png"), status: "待生成", qcScore: null, reviewed: false, frame: "16:9（横屏）", lens: "35mm（环境人像）", angle: "低机位", movement: "缓慢拉远", dialogue: "夜风吹过，他终于松开了手。", prompt: defaultPrompt, characterIds: ["C001"], outfitId: "O001", cost: 0, versions: [] },
  ],
  assets: {
    characters: [
      { id: "C001", name: "林泽", meta: "男主｜28岁", description: "黑发，克制冷静，创业者。", image: asset("shot-hero.png"), status: "已锁定" },
      { id: "C002", name: "苏晴", meta: "女主｜26岁", description: "长发，外冷内热，身份成谜。", image: asset("shot-woman.png"), status: "已锁定" },
    ],
    locations: [
      { id: "L001", name: "城市天台", meta: "夜景｜主场景", description: "可俯瞰江面与城市天际线。", image: asset("shot-wide.png"), status: "已锁定" },
    ],
    props: [
      { id: "P001", name: "旧照片", meta: "剧情道具", description: "承载林泽与苏晴的过去。", image: asset("shot-woman.png"), status: "待确认" },
    ],
  },
  tasks: [
    { id: "T9382", shotId: "SH044", type: "视频", model: "Seedance", status: "Success", cost: 0.72, createdAt: "2026-09-26 09:35" },
    { id: "T9381", shotId: "SH043", type: "视频", model: "Kling", status: "Success", cost: 0.81, createdAt: "2026-09-26 09:30" },
    { id: "T9380", shotId: "SH042", type: "视频", model: "Vidu", status: "Failed", cost: 0.42, createdAt: "2026-09-26 09:25" },
  ],
};

export { defaultPrompt };
