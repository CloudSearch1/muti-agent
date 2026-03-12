/**
 * 数据表格组件
 * 支持排序、筛选、分页、选择等功能
 */

export const DataTable = {
    name: 'DataTable',
    
    props: {
        columns: {
            type: Array,
            required: true
            // [{ key: 'name', title: '名称', sortable: true, width: '200px', align: 'left' }]
        },
        data: {
            type: Array,
            default: () => []
        },
        loading: {
            type: Boolean,
            default: false
        },
        selectable: {
            type: Boolean,
            default: false
        },
        selectedKeys: {
            type: Array,
            default: () => []
        },
        rowKey: {
            type: String,
            default: 'id'
        },
        emptyText: {
            type: String,
            default: '暂无数据'
        },
        stripe: {
            type: Boolean,
            default: true
        },
        hover: {
            type: Boolean,
            default: true
        },
        border: {
            type: Boolean,
            default: true
        }
    },
    
    emits: ['update:selectedKeys', 'sort-change', 'row-click', 'selection-change'],
    
    template: `
        <div class="overflow-x-auto">
            <table :class="['w-full text-sm', border ? 'border border-gh-border rounded-lg overflow-hidden' : '']">
                <thead>
                    <tr class="bg-gh-elevated">
                        <!-- 选择列 -->
                        <th v-if="selectable" class="w-12 px-4 py-3 text-left">
                            <input type="checkbox" 
                                   :checked="isAllSelected"
                                   :indeterminate="isIndeterminate"
                                   @change="toggleSelectAll"
                                   class="w-4 h-4 rounded border-gh-border bg-gh-bg text-gh-blue focus:ring-gh-blue">
                        </th>
                        
                        <!-- 数据列 -->
                        <th v-for="col in columns" 
                            :key="col.key"
                            :style="{ width: col.width, textAlign: col.align || 'left' }"
                            :class="['px-4 py-3 font-semibold text-gh-light whitespace-nowrap', col.sortable ? 'cursor-pointer hover:text-white select-none' : '']"
                            @click="col.sortable && handleSort(col.key)">
                            <div class="flex items-center gap-1" :class="{ 'justify-center': col.align === 'center' }">
                                {{ col.title }}
                                <span v-if="col.sortable" class="text-xs">
                                    <i v-if="sortKey === col.key" 
                                       :class="['fas', sortOrder === 'asc' ? 'fa-sort-up' : 'fa-sort-down']">
                                    </i>
                                    <i v-else class="fas fa-sort text-gh-text opacity-30"></i>
                                </span>
                            </div>
                        </th>
                    </tr>
                </thead>
                <tbody>
                    <tr v-if="loading">
                        <td :colspan="totalColumns" class="px-4 py-12 text-center text-gh-text">
                            <i class="fas fa-circle-notch fa-spin mr-2"></i>加载中...
                        </td>
                    </tr>
                    
                    <tr v-else-if="sortedData.length === 0">
                        <td :colspan="totalColumns" class="px-4 py-12 text-center text-gh-text">
                            <div class="flex flex-col items-center gap-3">
                                <i class="fas fa-inbox text-3xl opacity-30"></i>
                                <span>{{ emptyText }}</span>
                            </div>
                        </td>
                    </tr>
                    
                    <tr v-for="(row, index) in sortedData" 
                        :key="row[rowKey]"
                        :class="[
                            'transition cursor-pointer',
                            stripe && index % 2 === 1 ? 'bg-gh-bg/50' : '',
                            hover ? 'hover:bg-gh-elevated/50' : '',
                            isSelected(row) ? 'bg-gh-blue/10' : ''
                        ]"
                        @click="handleRowClick(row)">
                        <!-- 选择列 -->
                        <td v-if="selectable" class="px-4 py-3" @click.stop>
                            <input type="checkbox" 
                                   :checked="isSelected(row)"
                                   @change="toggleSelect(row)"
                                   class="w-4 h-4 rounded border-gh-border bg-gh-bg text-gh-blue focus:ring-gh-blue">
                        </td>
                        
                        <!-- 数据列 -->
                        <td v-for="col in columns" 
                            :key="col.key"
                            :style="{ textAlign: col.align || 'left' }"
                            class="px-4 py-3 text-gh-light">
                            <slot :name="col.key" :row="row" :value="row[col.key]">
                                {{ formatValue(row[col.key], col) }}
                            </slot>
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
    `,
    
    data() {
        return {
            sortKey: '',
            sortOrder: 'asc' // asc, desc
        };
    },
    
    computed: {
        totalColumns() {
            return this.columns.length + (this.selectable ? 1 : 0);
        },
        
        sortedData() {
            if (!this.sortKey) return this.data;
            
            const key = this.sortKey;
            const order = this.sortOrder === 'asc' ? 1 : -1;
            
            return [...this.data].sort((a, b) => {
                let aVal = a[key];
                let bVal = b[key];
                
                if (typeof aVal === 'string') {
                    aVal = aVal.toLowerCase();
                    bVal = bVal.toLowerCase();
                }
                
                if (aVal < bVal) return -1 * order;
                if (aVal > bVal) return 1 * order;
                return 0;
            });
        },
        
        isAllSelected() {
            return this.data.length > 0 && this.data.every(row => this.isSelected(row));
        },
        
        isIndeterminate() {
            const selectedCount = this.data.filter(row => this.isSelected(row)).length;
            return selectedCount > 0 && selectedCount < this.data.length;
        }
    },
    
    methods: {
        formatValue(value, column) {
            if (value === null || value === undefined) return '--';
            if (column.formatter) return column.formatter(value);
            return value;
        },
        
        isSelected(row) {
            return this.selectedKeys.includes(row[this.rowKey]);
        },
        
        toggleSelect(row) {
            const key = row[this.rowKey];
            const index = this.selectedKeys.indexOf(key);
            const newSelection = [...this.selectedKeys];
            
            if (index > -1) {
                newSelection.splice(index, 1);
            } else {
                newSelection.push(key);
            }
            
            this.$emit('update:selectedKeys', newSelection);
            this.$emit('selection-change', newSelection);
        },
        
        toggleSelectAll() {
            const newSelection = this.isAllSelected 
                ? [] 
                : this.data.map(row => row[this.rowKey]);
            
            this.$emit('update:selectedKeys', newSelection);
            this.$emit('selection-change', newSelection);
        },
        
        handleSort(key) {
            if (this.sortKey === key) {
                this.sortOrder = this.sortOrder === 'asc' ? 'desc' : 'asc';
            } else {
                this.sortKey = key;
                this.sortOrder = 'asc';
            }
            
            this.$emit('sort-change', { key: this.sortKey, order: this.sortOrder });
        },
        
        handleRowClick(row) {
            this.$emit('row-click', row);
        }
    }
};

export default DataTable;
