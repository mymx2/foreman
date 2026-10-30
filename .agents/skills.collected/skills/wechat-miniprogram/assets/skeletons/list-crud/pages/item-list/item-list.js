const { createLocalItemStore } = require('../../utils/item-store');

const store = createLocalItemStore({
    storageKey: 'mini-program-skeleton-item-list',
});

Page({
    data: {
        title: '列表增删改骨架',
        subtitle: '点击列表项可编辑，右侧按钮可删除',
        viewState: 'loading',
        errorMessage: '加载失败，请稍后重试',
        items: [],
        showEditor: false,
        editorMode: 'create',
        editorTitle: '新增记录',
        editingId: '',
        formTitle: '',
        formNote: '',
        formError: '',
        submitting: false,
    },

    onLoad() {
        this.loadItems();
    },

    handleRetry() {
        this.loadItems();
    },

    loadItems() {
        this.setData({
            viewState: 'loading',
            errorMessage: '',
        });

        store.list().then(result => {
            if (result.error) {
                this.setData({
                    viewState: 'error',
                    errorMessage: result.error.message || '加载失败，请稍后重试',
                });
                return;
            }

            const source = Array.isArray(result.data) ? result.data : [];
            const items = source.map(mapViewItem);
            this.setData({
                items,
                viewState: items.length === 0 ? 'empty' : 'ready',
            });
        });
    },

    openCreate() {
        this.setData({
            showEditor: true,
            editorMode: 'create',
            editorTitle: '新增记录',
            editingId: '',
            formTitle: '',
            formNote: '',
            formError: '',
            submitting: false,
        });
    },

    openEdit(event) {
        const itemId = event.currentTarget.dataset.id;
        const item = this.findItemById(itemId);
        if (!item) {
            return;
        }

        this.setData({
            showEditor: true,
            editorMode: 'edit',
            editorTitle: '编辑记录',
            editingId: item.id,
            formTitle: item.title,
            formNote: item.note,
            formError: '',
            submitting: false,
        });
    },

    closeEditor() {
        if (this.data.submitting) {
            return;
        }
        this.setData({
            showEditor: false,
            formError: '',
        });
    },

    handleTitleInput(event) {
        this.setData({
            formTitle: event.detail.value,
            formError: '',
        });
    },

    handleNoteInput(event) {
        this.setData({
            formNote: event.detail.value,
            formError: '',
        });
    },

    handleSave() {
        if (this.data.submitting) {
            return;
        }

        const title = typeof this.data.formTitle === 'string' ? this.data.formTitle.trim() : '';
        if (title === '') {
            this.setData({ formError: '请填写标题' });
            return;
        }

        const payload = {
            title,
            note: this.data.formNote,
        };

        const request = this.data.editorMode === 'edit'
            ? store.update(this.data.editingId, payload)
            : store.create(payload);

        this.setData({
            submitting: true,
            formError: '',
        });

        request.then(result => {
            if (result.error) {
                this.setData({
                    formError: result.error.message || '保存失败，请稍后重试',
                    submitting: false,
                });
                return;
            }

            this.setData({
                showEditor: false,
                submitting: false,
            });
            this.loadItems();
        });
    },

    handleDelete(event) {
        const itemId = event.currentTarget.dataset.id;
        if (!itemId) {
            return;
        }

        wx.showModal({
            title: '确认删除',
            content: '删除后不可恢复，是否继续？',
            confirmColor: '#1769e0',
            success: result => {
                if (!result.confirm) {
                    return;
                }
                this.removeItem(itemId);
            },
        });
    },

    removeItem(itemId) {
        store.remove(itemId).then(result => {
            if (result.error) {
                wx.showToast({
                    title: result.error.message || '删除失败，请稍后重试',
                    icon: 'none',
                });
                return;
            }
            this.loadItems();
        });
    },

    findItemById(itemId) {
        const items = this.data.items || [];
        for (let i = 0; i < items.length; i += 1) {
            if (items[i].id === itemId) {
                return items[i];
            }
        }
        return null;
    },
});

function mapViewItem(item) {
    const title = typeof item.title === 'string' && item.title.trim() !== '' ? item.title.trim() : '未命名';
    const note = typeof item.note === 'string' ? item.note : '';
    return {
        id: String(item.id),
        title,
        note,
        noteText: note === '' ? '暂无备注' : note,
        updatedText: formatTime(item.updatedAt),
    };
}

function formatTime(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return '刚刚更新';
    }
    const year = String(date.getFullYear());
    const month = pad(date.getMonth() + 1);
    const day = pad(date.getDate());
    const hours = pad(date.getHours());
    const minutes = pad(date.getMinutes());
    return year + '-' + month + '-' + day + ' ' + hours + ':' + minutes;
}

function pad(value) {
    return value < 10 ? '0' + String(value) : String(value);
}
