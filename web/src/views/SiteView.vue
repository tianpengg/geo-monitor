<script setup lang="ts">
import { computed } from 'vue'
import { useWorkspaceContext } from '../composables/workspaceContext'
import { timezoneOptions } from '../utils/timezones'
import UiIcon from '../components/ui/UiIcon.vue'
import UiInput from '../components/ui/UiInput.vue'
import UiSelect from '../components/ui/UiSelect.vue'

const {
  busy,
  site,
  domain,
  aliasDomains,
  timezone,
  ipMode,
  credentials,
  copied,
  ipOptions,
  healthState,
  installCommand,
  saveSite,
  generateCredentials,
  copy,
} = useWorkspaceContext()
const zoneOptions = computed(() => timezoneOptions(timezone.value))
</script>

<template>
<div class="setup-grid">
    <section class="panel content-panel">
      <div class="section-titlebar">
        <div>
          <h2 class="section-heading">连接你的官网</h2>
          <p class="section-subtitle">一个官网 · 一条独立日志来源</p>
        </div>
        <UiIcon name="world" />
      </div>
      <form novalidate class="stack-form site-form" @submit.prevent="saveSite">
        <label
          >官网域名<UiInput
            v-model="domain"
            icon="world"
            clearable
            aria-label="官网域名"
            placeholder="www.example.com"
            required
            :disabled="busy"
          /><small>填写域名，不包含协议、端口或路径。</small></label>
        <label>官网别名（可选）<UiInput
            v-model="aliasDomains"
            multiline
            rows="2"
            aria-label="官网别名"
            aria-describedby="siteAliasHelp"
            placeholder="www.example.com"
            maxlength="2600"
            spellcheck="false"
            :disabled="busy"
          /><small id="siteAliasHelp">同一官网使用的其他域名，每行一个或用逗号分隔，最多 10 个。只填域名；保存后，Sitemap 和手动导入会接受这些域名的页面并按路径合并。</small></label>
        <p class="notice neutral">www 与不带 www 的域名需要明确登记，未登记的子域不会自动放行。此处不修改 Nginx、主域名或采集器，也不能拆分混合多站日志。</p>
        <label
          >统计时区<UiSelect
            v-model="timezone"
            :options="zoneOptions"
            searchable
            aria-label="统计时区"
            aria-describedby="siteTimezoneHelp"
            :disabled="busy" /><small id="siteTimezoneHelp">决定“今天”、每日趋势和访问时间按哪个地区显示。中国大陆一般选北京时间；地区时区会按当地规则处理夏令时。</small></label
        ><label
          >日志中的 IP 是真实访问者吗？<UiSelect
            v-model="ipMode"
            :options="ipOptions"
            :disabled="busy"
            aria-label="日志 IP 确认状态"
            aria-describedby="siteIpHelp"
          /><small id="siteIpHelp">指 Nginx 访问日志第一列的 IP，用来核验爬虫来源。经过 CDN 或反向代理时，它可能是代理服务器的 IP。</small></label>
        <p class="notice neutral site-ip-guidance" aria-live="polite">{{ ipMode === 'unknown' ? '不确定就保持“还不确定”：日志采集和 UA 识别照常进行，来源核验显示“客户端 IP 不可确认”。' : '仅在已确认日志记录真实访问者 IP 时选择此项。后续请求还需命中有效的官方 IP 清单，才能标为“已核验”；历史结果不回算。' }}</p>
        <details class="site-ip-help">
          <summary><UiIcon name="chevron-right" />用了 CDN 或反向代理，怎么判断？</summary>
          <p>访问者 → CDN / 代理 → 官网服务器。如果日志记的是 CDN / 代理的 IP，先选“还不确定”。请管理员确认日志已正确还原真实访问者 IP，并限制可信代理后，再选“已确认”。</p>
          <p>这个选项只声明日志地址是否可信，不会自动修改 Nginx、CDN 或代理配置。</p>
        </details>
        <button class="primary-button" :disabled="busy">
          {{ busy ? '正在保存…' : '保存官网' }}
        </button>
      </form>
    </section>
    <section class="panel content-panel installation-note">
      <span class="step-label">安装前准备</span>
      <h2 class="section-heading">使用官网独立的访问日志</h2>
      <p>
        支持 Linux / 宝塔 + Docker，日志格式为 Nginx
        Combined。采集器以只读方式读取安装后的新增日志。
      </p>
      <ol>
        <li>确认日志仅包含当前官网的请求。</li>
        <li>准备日志文件的绝对路径与读取权限。</li>
        <li>保存官网配置，生成凭据后执行安装命令。</li>
      </ol>
      <p class="notice neutral">标准 Combined 日志没有域名字段，混合日志不能可靠分站。</p>
    </section>
  </div>
  <section v-if="site" class="panel content-panel installation-panel">
    <div class="section-titlebar">
      <div>
        <h2 class="section-heading">安装采集器</h2>
        <p class="section-subtitle">在官网日志所在服务器执行安装</p>
      </div>
      <span class="badge" :class="healthState.tone">{{ healthState.label }}</span>
    </div>
    <dl class="info-list identifiers">
      <div>
        <dt>网站标识</dt>
        <dd>
          <code>{{ site.id }}</code>
        </dd>
      </div>
      <div>
        <dt>日志来源标识</dt>
        <dd>
          <code>{{ site.source_id }}</code>
        </dd>
      </div>
    </dl>
    <p class="paragraph muted">
      完整凭据仅在生成后的当前页面展示。重新生成会使旧凭据失效，需要更新采集器配置。
    </p>
    <button class="secondary-button" :disabled="busy" @click="generateCredentials">
      <UiIcon name="shield-check" />生成／重置采集凭据
    </button>
    <div v-if="credentials" class="credentials-panel">
      <div class="section-titlebar">
        <label for="collectorToken">采集凭据</label
        ><button class="text-button" :disabled="busy" @click="copy(credentials.token, 'token')">
          {{ copied === 'token' ? '已复制凭据' : '复制凭据' }}
        </button>
      </div>
      <UiInput
        id="collectorToken"
        multiline
        readonly
        rows="2"
        :model-value="credentials.token"
        spellcheck="false"
      />
      <div class="section-titlebar">
        <label for="installCommand">安装命令</label
        ><button class="text-button" :disabled="busy" @click="copy(installCommand, 'command')">
          {{ copied === 'command' ? '已复制命令' : '复制命令' }}
        </button>
      </div>
      <UiInput
        id="installCommand"
        aria-label="采集器安装命令"
        multiline
        readonly
        rows="4"
        :model-value="installCommand"
        spellcheck="false"
      />
      <p class="muted paragraph">
        按安装提示输入日志绝对路径和采集凭据。脚本会检查
        Docker、格式、权限和连接；停止和重连会保留读取位置。
      </p>
    </div>
  </section>
</template>
