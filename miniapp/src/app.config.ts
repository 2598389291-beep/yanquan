// 言权小程序全局配置
export default defineAppConfig({
  pages: [
    'pages/home/index',
    'pages/compose/index',
    'pages/history/index',
    'pages/profile/index',
    'pages/detail/index',
    'pages/guide/index',
    'pages/login/index',
    'pages/agreement/index',
    'pages/onboard/index',
  ],
  window: {
    backgroundTextStyle: 'light',
    navigationBarBackgroundColor: '#0F2B4C',
    navigationBarTitleText: '言权',
    navigationBarTextStyle: 'white',
    backgroundColor: '#F4F6FA',
  },
  tabBar: {
    color: '#8B98AB',
    selectedColor: '#B8923C',
    backgroundColor: '#FFFFFF',
    borderStyle: 'white',
    list: [
      {
        pagePath: 'pages/home/index',
        text: '首页',
        iconPath: 'assets/tabbar/home.png',
        selectedIconPath: 'assets/tabbar/home-selected.png',
      },
      {
        pagePath: 'pages/history/index',
        text: '记录',
        iconPath: 'assets/tabbar/history.png',
        selectedIconPath: 'assets/tabbar/history-selected.png',
      },
      {
        pagePath: 'pages/profile/index',
        text: '我的',
        iconPath: 'assets/tabbar/profile.png',
        selectedIconPath: 'assets/tabbar/profile-selected.png',
      },
    ],
  },
})
