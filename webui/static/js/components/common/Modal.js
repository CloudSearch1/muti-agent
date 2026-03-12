/**
 * 模态框组件
 * 可复用的模态框基础组件
 */

export const Modal = {
    name: 'Modal',
    
    props: {
        visible: {
            type: Boolean,
            default: false
        },
        title: {
            type: String,
            default: ''
        },
        width: {
            type: String,
            default: '500px'
        },
        closable: {
            type: Boolean,
            default: true
        },
        maskClosable: {
            type: Boolean,
            default: true
        },
        showFooter: {
            type: Boolean,
            default: true
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
        },
        confirmDisabled: {
            type: Boolean,
            default: false
        }
    },
    
    emits: ['update:visible', 'confirm', 'cancel', 'close'],
    
    template: `
        <teleport to="body">
            <transition name="modal">
                <div v-if="visible" 
                     class="fixed inset-0 z-50 flex items-center justify-center p-4"
                     @click="handleMaskClick">
                    <!-- 遮罩 -->
                    <div class="absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity"></div>
                    
                    <!-- 内容 -->
                    <div class="relative bg-gh-canvas rounded-xl shadow-2xl border border-gh-border w-full overflow-hidden"
                         :style="{ maxWidth: width }"
                         @click.stop>
                        <!-- 头部 -->
                        <div v-if="title || closable" class="flex items-center justify-between px-6 py-4 border-b border-gh-border">
                            <h3 class="text-lg font-semibold text-white">{{ title }}</h3>
                            <button v-if="closable" 
                                    @click="handleClose"
                                    class="w-8 h-8 flex items-center justify-center rounded-lg text-gh-text hover:text-white hover:bg-gh-elevated transition">
                                <i class="fas fa-times"></i>
                            </button>
                        </div>
                        
                        <!-- 主体 -->
                        <div class="px-6 py-4 max-h-[70vh] overflow-y-auto">
                            <slot></slot>
                        </div>
                        
                        <!-- 底部 -->
                        <div v-if="showFooter" class="flex items-center justify-end gap-3 px-6 py-4 border-t border-gh-border bg-gh-elevated/30">
                            <button @click="handleCancel" class="btn-secondary">
                                {{ cancelText }}
                            </button>
                            <button @click="handleConfirm" 
                                    :disabled="confirmDisabled || confirmLoading"
                                    :class="['btn-primary flex items-center gap-2', (confirmDisabled || confirmLoading) ? 'opacity-50 cursor-not-allowed' : '']">
                                <i v-if="confirmLoading" class="fas fa-circle-notch fa-spin"></i>
                                {{ confirmText }}
                            </button>
                        </div>
                    </div>
                </div>
            </transition>
        </teleport>
    `,
    
    methods: {
        handleMaskClick() {
            if (this.maskClosable) {
                this.handleClose();
            }
        },
        
        handleClose() {
            this.$emit('update:visible', false);
            this.$emit('close');
        },
        
        handleCancel() {
            this.$emit('cancel');
            this.handleClose();
        },
        
        handleConfirm() {
            this.$emit('confirm');
        }
    },
    
    watch: {
        visible(val) {
            if (val) {
                document.body.style.overflow = 'hidden';
            } else {
                document.body.style.overflow = '';
            }
        }
    }
};

export default Modal;
