/**
 * IntelliTeam WebSocket 实时更新模块
 *
 * 功能：
 * - WebSocket 连接管理
 * - 自动重连
 * - 事件订阅
 * - 心跳检测
 */

class RealtimeManager {
    constructor(options = {}) {
        this.url = options.url || `ws://${window.location.host}/ws`;
        this.reconnectInterval = options.reconnectInterval || 3000;
        this.maxReconnectAttempts = options.maxReconnectAttempts || 5;
        this.heartbeatInterval = options.heartbeatInterval || 30000;

        this.ws = null;
        this.reconnectAttempts = 0;
        this.isConnecting = false;
        this.subscriptions = new Map();
        this.listeners = new Map();
        this.heartbeatTimer = null;

        // 状态
        this.state = {
            connected: false,
            connecting: false,
            error: null
        };

        // 自动连接
        if (options.autoConnect !== false) {
            this.connect();
        }
    }

    /**
     * 连接 WebSocket
     */
    connect() {
        if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
            return;
        }

        this.isConnecting = true;
        this.state.connecting = true;
        this.state.error = null;

        try {
            this.ws = new WebSocket(this.url);

            this.ws.onopen = () => {
                console.log('[RealtimeManager] WebSocket connected');
                this.isConnecting = false;
                this.reconnectAttempts = 0;
                this.state.connected = true;
                this.state.connecting = false;

                // 重新订阅
                this._resubscribe();

                // 启动心跳
                this._startHeartbeat();

                // 触发事件
                this._emit('connected');
            };

            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this._handleMessage(data);
                } catch (e) {
                    console.error('[RealtimeManager] Parse message error:', e);
                }
            };

            this.ws.onclose = (event) => {
                console.log('[RealtimeManager] WebSocket closed:', event.code, event.reason);
                this.state.connected = false;
                this.state.connecting = false;
                this._stopHeartbeat();
                this._emit('disconnected', { code: event.code, reason: event.reason });

                // 自动重连
                if (this.reconnectAttempts < this.maxReconnectAttempts) {
                    this._scheduleReconnect();
                }
            };

            this.ws.onerror = (error) => {
                console.error('[RealtimeManager] WebSocket error:', error);
                this.state.error = 'Connection error';
                this._emit('error', error);
            };

        } catch (error) {
            console.error('[RealtimeManager] Connect error:', error);
            this.state.error = error.message;
            this._scheduleReconnect();
        }
    }

    /**
     * 断开连接
     */
    disconnect() {
        this._stopHeartbeat();
        if (this.ws) {
            this.ws.close(1000, 'Client disconnect');
            this.ws = null;
        }
        this.state.connected = false;
    }

    /**
     * 订阅事件
     */
    subscribe(event, callback) {
        if (!this.subscriptions.has(event)) {
            this.subscriptions.set(event, new Set());
        }
        this.subscriptions.get(event).add(callback);

        // 发送订阅消息
        if (this.state.connected) {
            this._send({ type: 'subscribe', event });
        }

        return () => this.unsubscribe(event, callback);
    }

    /**
     * 取消订阅
     */
    unsubscribe(event, callback) {
        if (this.subscriptions.has(event)) {
            this.subscriptions.get(event).delete(callback);
            if (this.subscriptions.get(event).size === 0) {
                this.subscriptions.delete(event);
                // 发送取消订阅消息
                if (this.state.connected) {
                    this._send({ type: 'unsubscribe', event });
                }
            }
        }
    }

    /**
     * 监听事件
     */
    on(event, callback) {
        if (!this.listeners.has(event)) {
            this.listeners.set(event, new Set());
        }
        this.listeners.get(event).add(callback);

        return () => this.off(event, callback);
    }

    /**
     * 移除监听
     */
    off(event, callback) {
        if (this.listeners.has(event)) {
            this.listeners.get(event).delete(callback);
        }
    }

    /**
     * 发送消息
     */
    send(type, data = {}) {
        this._send({ type, ...data });
    }

    // ============ 私有方法 ============

    _send(message) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(message));
        }
    }

    _handleMessage(data) {
        const { type, event, payload } = data;

        // 处理心跳响应
        if (type === 'pong') {
            return;
        }

        // 触发订阅回调
        if (event && this.subscriptions.has(event)) {
            this.subscriptions.get(event).forEach(callback => {
                try {
                    callback(payload);
                } catch (e) {
                    console.error('[RealtimeManager] Callback error:', e);
                }
            });
        }

        // 触发通用监听
        if (type && this.listeners.has(type)) {
            this.listeners.get(type).forEach(callback => {
                try {
                    callback(data);
                } catch (e) {
                    console.error('[RealtimeManager] Listener error:', e);
                }
            });
        }
    }

    _resubscribe() {
        this.subscriptions.forEach((_, event) => {
            this._send({ type: 'subscribe', event });
        });
    }

    _startHeartbeat() {
        this._stopHeartbeat();
        this.heartbeatTimer = setInterval(() => {
            this._send({ type: 'ping' });
        }, this.heartbeatInterval);
    }

    _stopHeartbeat() {
        if (this.heartbeatTimer) {
            clearInterval(this.heartbeatTimer);
            this.heartbeatTimer = null;
        }
    }

    _scheduleReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.log('[RealtimeManager] Max reconnect attempts reached');
            this._emit('max_reconnect_failed');
            return;
        }

        this.reconnectAttempts++;
        const delay = this.reconnectInterval * Math.pow(1.5, this.reconnectAttempts - 1);

        console.log(`[RealtimeManager] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);

        setTimeout(() => {
            this.connect();
        }, delay);
    }

    _emit(event, data) {
        if (this.listeners.has(event)) {
            this.listeners.get(event).forEach(callback => {
                try {
                    callback(data);
                } catch (e) {
                    console.error('[RealtimeManager] Emit error:', e);
                }
            });
        }
    }
}

// 导出
if (typeof window !== 'undefined') {
    window.RealtimeManager = RealtimeManager;
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = RealtimeManager;
}