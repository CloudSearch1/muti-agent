/**
 * 确认对话框组件
 * 用于删除确认、操作确认等场景
 */

export const ConfirmDialog = {
    name: 'ConfirmDialog',
    
    props: {
        visible: {
            type: Boolean,
            default: false
        },
        title: {
            type: String,
            default: '确认操作'
        },
        message: {
            type: String,
            default: '您确定要执行此操作吗？'
        },
        type: {
            type: String,
            default: 'warning', // warning, danger, info
            validator: (value) => ['warning', 'danger', 'info'].includes(value)
        },
        confirmText: {
            type: String,
            default: '确定'
        },
        cancelText: {
            type: String,
            default: '取消'
        },
        confirmLoading: {
            type: Boolean,
            default: false
        }
    },
    
    emits: ['update:visible', 'confirm', 'cancel'],
    
    template: `
        <teleport to="body">
            <transition name="modal">
                <div v-if="visible" 
                     class="fixed inset-0 z-50 flex items-center justify-center p-4"
                     @click="handleCancel">
                    <div class="absolute inset-0 bg-black/60 backdrop-blur-sm"></div>
                    
                    <div class="relative bg-gh-canvas rounded-xl shadow-2xl border border-gh-border w-full max-w-md overflow-hidden"
                         @click.stop>
                        <div class="p-6">
                            <div class="flex items-start gap-4">
                                <div :class="['w-12 h-12 rounded-full flex items-center justify-center flex-shrink-0', iconBgClass]">
                                    <i :class="[iconClass, 'text-xl']"></i>
                                </div>
                                <div>
                                    <h3 class="text-lg font-semibold text-white mb-2">{{ title }}</h3>
                                    <p class="text-gh-text text-sm">{{ message }}</p>
                                </div>
                            </div>
                        </div>
                        
                        <div class="flex items-center justify-end gap-3 px-6 py-4 border-t border-gh-border bg-gh-elevated/30">
                            <button @click="handleCancel" class="btn-secondary">
                                {{ cancelText }}
                            </button>
                            <button @click="handleConfirm" 
                                    :disabled="confirmLoading"
                                    :class="['flex items-center gap-2', buttonClass]">
                                <i v-if="confirmLoading" class="fas fa-circle-notch fa-spin"></i>
                                {{ confirmText }}
                            </button>
                        </div>
                    </div>
                </div>
            </transition>
        </teleport>
    `,
    
    computed: {
        iconClass() {
            const icons = {
                warning: 'fas fa-exclamation-triangle text-yellow-500',
                danger: 'fas fa-exclamation-circle text-red-500',
                info: 'fas fa-info-circle text-blue-500'
            };
            return icons[this.type] || icons.warning;
        },
        
        iconBgClass() {
            const classes = {
                warning: 'bg-yellow-500/10',
                danger: 'bg-red-500/10',
                info: 'bg-blue-500/10'
            };
            return classes[this.type] || classes.warning;
        },
        
        buttonClass() {
            const classes = {
                warning: 'btn-primary',
                danger: 'btn-danger',
                info: 'btn-primary'
            };
            return classes[this.type] || classes.warning;
        }
    },
    
    methods: {
        handleCancel() {
            this.$emit('update:visible', false);
            this.$emit('cancel');
        },
        
        handleConfirm() {
            this.$emit('confirm');
        }
    }
};

export default ConfirmDialog;
