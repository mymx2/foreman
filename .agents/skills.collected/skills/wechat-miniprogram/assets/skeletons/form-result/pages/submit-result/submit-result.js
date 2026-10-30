Page({
    data: {
        status: 'fail',
        title: '提交失败',
        description: '请检查后重试，或稍后再提交。',
    },

    onLoad(options) {
        const status = options && options.status === 'success' ? 'success' : 'fail';
        if (status === 'success') {
            this.setData({
                status: 'success',
                title: '提交成功',
                description: '我们已收到你的信息，将尽快处理。',
            });
            return;
        }

        this.setData({
            status: 'fail',
            title: '提交失败',
            description: '请检查后重试，或稍后再提交。',
        });
    },

    goHome() {
        wx.reLaunch({
            url: '/pages/index/index',
        });
    },

    continueSubmit() {
        wx.redirectTo({
            url: '/pages/submit-form/submit-form',
        });
    },
});
