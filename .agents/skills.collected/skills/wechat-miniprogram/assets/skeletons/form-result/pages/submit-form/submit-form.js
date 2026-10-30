Page({
    data: {
        title: '信息提交',
        subtitle: '请填写基础信息后提交',
        name: '',
        contact: '',
        description: '',
        formError: '',
        fieldErrors: {
            name: '',
            contact: '',
            description: '',
        },
        submitting: false,
    },

    handleInput(event) {
        const field = event.currentTarget.dataset.field;
        if (!field) {
            return;
        }

        const update = {};
        update[field] = event.detail.value;
        update['fieldErrors.' + field] = '';
        update.formError = '';
        this.setData(update);
    },

    handleSubmit() {
        if (this.data.submitting) {
            return;
        }

        const validation = this.validate();
        if (!validation.valid) {
            this.setData({
                formError: validation.summary,
                fieldErrors: validation.fieldErrors,
            });
            return;
        }

        const values = {
            name: this.data.name.trim(),
            contact: this.data.contact.trim(),
            description: this.data.description.trim(),
        };

        this.setData({
            submitting: true,
            formError: '',
            fieldErrors: {
                name: '',
                contact: '',
                description: '',
            },
        });

        this.submit(values).then(
            result => {
                if (result && result.error) {
                    this.failSubmit(toMessage(result.error, '提交失败，请稍后重试'));
                    return;
                }
                this.finishSubmit();
            },
            error => {
                this.failSubmit(toMessage(error, '提交失败，请稍后重试'));
            },
        );
    },

    failSubmit(message) {
        this.setData({
            formError: message,
            submitting: false,
        });
    },

    // 保存已经成功，之后的跳转失败不能当成提交失败：否则用户会重复提交。
    // 跳转失败时留在本页，提示已提交，按钮保持禁用。
    finishSubmit() {
        wx.redirectTo({
            url: '/pages/submit-result/submit-result?status=success',
            fail: () => {
                this.setData({
                    formError: '已提交成功，请返回上一页查看结果',
                    submitting: true,
                });
            },
        });
    },

    validate() {
        const fieldErrors = {
            name: '',
            contact: '',
            description: '',
        };

        if (this.data.name.trim() === '') {
            fieldErrors.name = '请输入姓名';
        }
        if (this.data.contact.trim() === '') {
            fieldErrors.contact = '请输入联系方式';
        }

        const summary = fieldErrors.name || fieldErrors.contact || '';
        const valid = summary === '';
        return { valid, summary, fieldErrors };
    },

    submit(values) {
        // 替换点：将这里改成真实的保存逻辑（例如调用你自己的服务端接口）。
        // 当前仅用 Promise 模拟成功结果，方便直接复制后先跑通页面流程。
        return new Promise(resolve => {
            setTimeout(() => {
                resolve({ data: values, error: null });
            }, 400);
        });
    },
});

function toMessage(error, fallback) {
    if (error && typeof error === 'object' && typeof error.message === 'string' && error.message !== '') {
        return error.message;
    }
    return fallback;
}
