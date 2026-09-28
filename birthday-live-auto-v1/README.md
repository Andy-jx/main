# 生日直播自动说话 V1

这是第一版逻辑控制器，先把直播业务流程跑通，不改你现有的生日算法。

## 已实现
- 自动识别常见生日评论：5.27、5月27、1991/5/27、正月初六、农历六月十八等
- 按观众累计小红心数量
- 满 10 颗才进入生日处理队列
- 同一观众防重复处理
- 排队播报，避免多个声音重叠
- 70～100 秒随机提醒一次“小手指的地方点够10颗小红心，没点够的去补一下”
- 最近有人送礼时暂缓提醒
- 浏览器 TTS 自动说话，可选择系统声音
- 本场观众记录保存在 localStorage，刷新页面不丢
- 对直播监听程序预留 JS API 和 BroadcastChannel

## 先这样测试
1. 打开 index.html。
2. 点“开启自动模式”。
3. 右侧昵称填“测试观众”，评论填“5.27”，点“模拟评论”。
4. “加红心”填 10，点“模拟小红心”。
5. 页面会自动把这个人加入队列并播报。

## 接入你原来的生日 HTML
V1 预留了下面这个函数：

```js
window.submitBirthdayAuto = async function (payload) {
  // payload:
  // { uid, nickname, birthday, hearts }

  // 这里调用你现有 HTML 的“输入生日 -> 计算结果”原函数
  // 最后返回下面任意一种格式：

  return {
    birthdayText: "五月二十七羊",
    scoreText: "86分",
    speakText: payload.nickname + "，五月二十七，八十六分"
  };
};
```

只要接上这个函数，满 10 颗后就会自动调用你原来的生日算法并把结果念出来。

## 给后续直播监听器的数据接口
```js
BirthdayLiveAuto.comment({
  uid: "用户唯一ID",
  nickname: "张三",
  text: "5.27"
});

BirthdayLiveAuto.gift({
  uid: "用户唯一ID",
  nickname: "张三",
  count: 3,
  giftName: "小红心"
});
```

也可以通过：

```js
const bc = new BroadcastChannel("birthday-live-v1");
bc.postMessage({type:"comment", uid:"1", nickname:"张三", text:"5.27"});
bc.postMessage({type:"gift", uid:"1", nickname:"张三", count:10, giftName:"小红心"});
```

## 现在还没有接的部分
你上传的是 Windows 的 .lnk 快捷方式，不是 HTML 源文件本体，所以这一版还不能直接调用你截图里现有的“开始输入/生日计算”代码。

把真正的 `生日直播_独立数据版.html` 源文件接进来后，只需要补 `submitBirthdayAuto()` 适配层，不需要重做这套直播逻辑。
