// 強化部位
export const PARTS = [
  { id: 'full', name: '全身・有酸素', short: '全身', icon: '🔥', color: '#ff6a3d' },
  { id: 'lower', name: '下半身（脚・お尻）', short: '下半身', icon: '🦵', color: '#3d8bff' },
  { id: 'core', name: '腹筋・体幹', short: '腹筋・体幹', icon: '🎯', color: '#e8a100' },
  { id: 'upper', name: '上半身（胸・腕・肩）', short: '上半身', icon: '💪', color: '#e5446d' },
  { id: 'back', name: '背中・姿勢', short: '背中', icon: '🧘', color: '#1fae6b' },
];

export const PART_BY_ID = Object.fromEntries(PARTS.map((p) => [p.id, p]));

export const LEVELS = {
  1: { label: 'やさしい', dots: '●○○' },
  2: { label: 'ふつう', dots: '●●○' },
  3: { label: 'きつい', dots: '●●●' },
};
