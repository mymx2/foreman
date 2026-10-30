Page({
    data: {
        title: '个人中心',
        subtitle: '管理个人资料与常用入口',
        profile: {
            nickname: '',
            intro: '',
        },
        displayNickname: '未设置昵称',
        displayIntro: '这个人很低调，还没有留下简介',
        avatarText: '?',
        menuGroups: [
            {
                key: 'content',
                items: [
                    { key: 'my-content', text: '我的内容', path: '' },
                    { key: 'notice', text: '消息通知', path: '' },
                ],
            },
            {
                key: 'system',
                items: [
                    { key: 'settings', text: '设置', path: '/pages/settings/settings' },
                    { key: 'about', text: '关于', path: '/pages/about/about' },
                ],
            },
        ],
    },

    onShow() {
        this.loadProfile();
    },

    loadProfile() {
        // 替换点：请在这里改为真实资料来源（例如已登录用户信息），当前先使用默认空资料。
        const profile = {
            nickname: '',
            intro: '',
        };
        this.applyProfile(profile);
    },

    applyProfile(profile) {
        const normalized = normalizeProfile(profile);
        this.setData({
            profile: normalized,
            displayNickname: getDisplayNickname(normalized.nickname),
            displayIntro: getDisplayIntro(normalized.intro),
            avatarText: getAvatarText(normalized.nickname),
        });
    },

    handleMenuTap(event) {
        const dataset = event && event.currentTarget ? event.currentTarget.dataset : null;
        const groupIndex = Number(dataset ? dataset.group : -1);
        const itemIndex = Number(dataset ? dataset.index : -1);
        const group = this.data.menuGroups[groupIndex];
        const menuItem = group && Array.isArray(group.items) ? group.items[itemIndex] : null;
        if (!menuItem) {
            return;
        }

        if (!menuItem.path) {
            wx.showToast({
                title: '该功能暂未接入',
                icon: 'none',
            });
            return;
        }

        wx.navigateTo({
            url: menuItem.path,
            fail: () => {
                wx.showToast({
                    title: '页面暂未开放',
                    icon: 'none',
                });
            },
        });
    },
});

function normalizeProfile(profile) {
    const input = profile && typeof profile === 'object' ? profile : {};
    const nickname = typeof input.nickname === 'string' ? input.nickname.trim() : '';
    const intro = typeof input.intro === 'string' ? input.intro.trim() : '';
    return {
        nickname,
        intro,
    };
}

function getDisplayNickname(nickname) {
    return nickname === '' ? '未设置昵称' : nickname;
}

function getDisplayIntro(intro) {
    return intro === '' ? '这个人很低调，还没有留下简介' : intro;
}

function getAvatarText(nickname) {
    if (nickname === '') {
        return '?';
    }
    const chars = Array.from(nickname);
    return chars.length > 0 ? chars[0] : '?';
}
