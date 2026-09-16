import {
  ArrowLeft,
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  ChartLineUp,
  Check,
  CheckCircle,
  ChatCircleDots,
  Copy,
  Database,
  DotsThreeVertical,
  Microphone,
  ListChecks,
  Paperclip,
  Phone,
  Robot,
  ShieldCheck,
  Sparkle,
  Smiley,
  UserFocus,
  X,
} from "@phosphor-icons/react";
import { AnimatePresence, motion, useMotionValue, useSpring, useTransform } from "framer-motion";
import { useEffect, useState } from "react";
import type { FormEvent, MouseEvent as ReactMouseEvent, ReactNode } from "react";

const IMAGE_BASE =
  import.meta.env.VITE_MENU_IMAGE_BASE_URL ??
  "https://raw.githubusercontent.com/Garun-mp4/urban_taste_bot/main/assets/menu";

const images = {
  steak: `${IMAGE_BASE}/urban-classic.png`,
  pasta: `${IMAGE_BASE}/seafood-pasta.png`,
  soup: `${IMAGE_BASE}/mushroom-cream-soup.png`,
  cheesecake: `${IMAGE_BASE}/urban-cheesecake.png`,
};

type ScenarioId = "reservation" | "menu" | "question";

type Scenario = {
  id: ScenarioId;
  label: string;
  query: string;
  response: string;
  meta: string[];
  result: string;
  quickReplies: { label: string; next: ScenarioId }[];
};

const scenarios: Scenario[] = [
  {
    id: "reservation",
    label: "Бронирование",
    query: "Можно забронировать столик сегодня вечером?",
    response:
      "Конечно. Соберу имя, количество гостей, дату, время и телефон — затем передам заявку администратору.",
    meta: ["имя", "гости", "дата", "время", "телефон"],
    result: "Заявка NEW в CRM",
    quickReplies: [
      { label: "Забронировать столик", next: "reservation" },
      { label: "Узнать меню", next: "menu" },
      { label: "Задать вопрос", next: "question" },
    ],
  },
  {
    id: "menu",
    label: "Меню",
    query: "Что у вас есть из блюд без мяса?",
    response:
      "В базе Urban Taste указаны вегетарианские блюда. Актуальный состав позиций подскажет администратор, если нужно уточнение.",
    meta: ["база знаний", "без выдумок", "уточнение"],
    result: "Точный ответ из контекста",
    quickReplies: [
      { label: "Забронировать столик", next: "reservation" },
      { label: "Узнать меню", next: "menu" },
      { label: "Задать вопрос", next: "question" },
    ],
  },
  {
    id: "question",
    label: "Сложный вопрос",
    query: "Сколько стоит банкет на 30 человек?",
    response:
      "Точной стоимости банкета нет в базе знаний. Передам вопрос администратору, чтобы вы получили корректный расчёт.",
    meta: ["нет данных", "эскалация", "администратор"],
    result: "Обращение question",
    quickReplies: [
      { label: "Забронировать столик", next: "reservation" },
      { label: "Узнать меню", next: "menu" },
      { label: "Задать вопрос", next: "question" },
    ],
  },
];

const architectureLayers = [
  {
    id: "input",
    number: "01",
    label: "Вход",
    title: "Клиент пишет как обычно",
    text: "Команда, reply-кнопка или свободное сообщение — сценарий начинается там, где человеку удобно.",
    icon: ChatCircleDots,
  },
  {
    id: "context",
    number: "02",
    label: "Контекст",
    title: "AI отвечает в границах базы",
    text: "Системный контекст Urban Taste отделяет подтверждённые факты от вопросов, которые нужно уточнить.",
    icon: Robot,
  },
  {
    id: "crm",
    number: "03",
    label: "CRM",
    title: "Заявка получает статус",
    text: "История диалога, клиент и обращение сохраняются в PostgreSQL. Состояния сценария держит Redis.",
    icon: Database,
  },
  {
    id: "owner",
    number: "04",
    label: "Владелец",
    title: "Важное приходит в очередь",
    text: "Администратор видит новую заявку, может взять её в работу, ответить клиенту и закрыть обращение.",
    icon: UserFocus,
  },
];

const fitOptions = [
  {
    id: "restaurant",
    label: "Ресторан",
    title: "Когда у бизнеса есть повторяющиеся вопросы",
    text: "Бронь, адрес, часы работы, меню и мероприятия собираются в один понятный маршрут без постоянного копирования ответов.",
    note: "Ближайший сценарий к Urban Taste",
  },
  {
    id: "beauty",
    label: "Сфера услуг",
    title: "Когда запись начинается в чате",
    text: "Салон, студия или мастерская могут квалифицировать запрос, собрать детали и передать его человеку с контекстом.",
    note: "Подходит для записи и консультаций",
  },
  {
    id: "education",
    label: "Обучение",
    title: "Когда важно не потерять обращение",
    text: "Бот отвечает на базовые вопросы о формате и собирает заявку на консультацию, не выдавая неподтверждённые условия.",
    note: "Подходит для первичной квалификации",
  },
  {
    id: "local",
    label: "Локальный бизнес",
    title: "Когда владелец сам держит операционку",
    text: "Мини-CRM в Telegram даёт небольшому бизнесу порядок в обращениях без отдельного сложного интерфейса на старте.",
    note: "Подходит для компактной команды",
  },
];

const ease = [0.32, 0.72, 0, 1] as const;

function Logo() {
  return (
    <a className="brand" href="#top" aria-label="Urban Taste — в начало кейса">
      <span className="brand-mark">UT</span>
      <span className="brand-name">Urban Taste</span>
      <span className="brand-caption">case 01</span>
    </a>
  );
}

function SectionLabel({ index, label }: { index: string; label: string }) {
  return (
    <div className="section-label">
      <span>{index}</span>
      <span className="section-label-rule" />
      <span>{label}</span>
    </div>
  );
}

function Reveal({ children, className = "", delay = 0 }: { children: ReactNode; className?: string; delay?: number }) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 28 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.18 }}
      transition={{ duration: 0.8, delay, ease }}
    >
      {children}
    </motion.div>
  );
}

function MagneticLink({
  children,
  href,
  variant = "primary",
  className = "",
  external = false,
}: {
  children: ReactNode;
  href: string;
  variant?: "primary" | "secondary" | "quiet";
  className?: string;
  external?: boolean;
}) {
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const springX = useSpring(x, { stiffness: 160, damping: 18 });
  const springY = useSpring(y, { stiffness: 160, damping: 18 });
  const iconX = useTransform(springX, [-12, 12], [-2, 2]);
  const iconY = useTransform(springY, [-12, 12], [-2, 2]);

  const handleMove = (event: ReactMouseEvent<HTMLAnchorElement>) => {
    const bounds = event.currentTarget.getBoundingClientRect();
    x.set((event.clientX - (bounds.left + bounds.width / 2)) / 9);
    y.set((event.clientY - (bounds.top + bounds.height / 2)) / 9);
  };

  const reset = () => {
    x.set(0);
    y.set(0);
  };

  return (
    <motion.a
      className={`button button-${variant} ${className}`}
      href={href}
      target={external ? "_blank" : undefined}
      rel={external ? "noreferrer" : undefined}
      style={{ x: springX, y: springY }}
      onMouseMove={handleMove}
      onMouseLeave={reset}
      whileTap={{ scale: 0.98, y: 1 }}
    >
      <span>{children}</span>
      {variant !== "quiet" && (
        <motion.span className="button-icon" style={{ x: iconX, y: iconY }}>
          <ArrowUpRight size={17} weight="regular" />
        </motion.span>
      )}
    </motion.a>
  );
}

function Nav() {
  const [open, setOpen] = useState(false);
  const links = [
    ["Сценарий", "#flow"],
    ["Система", "#system"],
    ["Для кого", "#fit"],
  ];

  return (
    <>
      <header className="site-header">
        <div className="nav-shell">
          <Logo />
          <nav className="desktop-nav" aria-label="Навигация по кейсу">
            {links.map(([label, href]) => (
              <a key={href} href={href}>
                {label}
              </a>
            ))}
          </nav>
          <MagneticLink href="#contact" className="nav-cta">
            Обсудить бота
          </MagneticLink>
          <button
            className={`menu-toggle ${open ? "is-open" : ""}`}
            type="button"
            aria-label={open ? "Закрыть меню" : "Открыть меню"}
            aria-expanded={open}
            onClick={() => setOpen((value) => !value)}
          >
            <span />
            <span />
          </button>
        </div>
      </header>
      <AnimatePresence>
        {open && (
          <motion.div
            className="mobile-menu"
            initial={{ opacity: 0, y: -14 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -14 }}
            transition={{ duration: 0.42, ease }}
          >
            <div className="mobile-menu-inner">
              {links.map(([label, href], index) => (
                <motion.a
                  key={href}
                  href={href}
                  initial={{ opacity: 0, y: 18 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.5, delay: index * 0.07, ease }}
                  onClick={() => setOpen(false)}
                >
                  <span>0{index + 1}</span>
                  {label}
                  <ArrowUpRight size={22} weight="regular" />
                </motion.a>
              ))}
              <a className="mobile-menu-cta" href="#contact" onClick={() => setOpen(false)}>
                Обсудить похожий сценарий <ArrowUpRight size={18} weight="regular" />
              </a>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

function Hero() {
  return (
    <section id="top" className="hero section-shell">
      <div className="hero-copy">
        <Reveal>
          <div className="eyebrow">
            <span className="eyebrow-dot" />
            CASE 01 / AI TELEGRAM CRM
          </div>
          <h1>
            Из диалога
            <br />
            <span>в заявку.</span>
          </h1>
          <p className="hero-lede">
            Urban Taste — AI-ассистент для ресторана, который отвечает по базе знаний, собирает бронь и не оставляет
            важные обращения в общем чате.
          </p>
          <div className="hero-actions">
            <MagneticLink href="#flow">Посмотреть сценарий</MagneticLink>
            <a className="text-link" href="#contact">
              Собрать похожего бота <ArrowRight size={18} weight="regular" />
            </a>
          </div>
          <div className="hero-proof">
            <span className="proof-line" />
            <span>Реальный кейс: Telegram + OpenAI API + PostgreSQL</span>
          </div>
        </Reveal>
      </div>
      <Reveal className="hero-stage" delay={0.12}>
        <div className="stage-heading">
          <span>Витрина результата</span>
          <span>живой сценарий</span>
        </div>
        <div className="hero-visual-shell">
          <div className="hero-visual">
            <img src={images.steak} alt="Студийная фотография стейка Urban Classic" fetchPriority="high" />
            <div className="image-pill image-pill-top">Urban Classic</div>
            <div className="image-caption">
              <span>Подтверждённая позиция</span>
              <span className="caption-arrow">
                <ArrowUpRight size={15} weight="regular" />
              </span>
            </div>
            <div className="hero-chat hero-chat-client">
              <span className="chat-avatar client-avatar">G</span>
              <span>Хочу столик на сегодня</span>
            </div>
            <div className="hero-chat hero-chat-bot">
              <span className="chat-avatar bot-avatar">
                <Robot size={14} weight="regular" />
              </span>
              <span>Соберу данные и передам заявку</span>
            </div>
          </div>
        </div>
        <div className="stage-footnote">
          <span className="status-dot" />
          Бот отвечает клиенту, CRM держит контекст, администратор получает сигнал.
        </div>
      </Reveal>
    </section>
  );
}

function CaseRibbon() {
  return (
    <section className="case-ribbon" aria-label="Технологии кейса">
      <div className="ribbon-inner section-shell">
        <span className="ribbon-label">Собрано как продукт</span>
        <div className="ribbon-items">
          <span>Python 3.12</span>
          <span>aiogram 3</span>
          <span>OpenAI API</span>
          <span>PostgreSQL</span>
          <span>Redis</span>
          <span>Docker Compose</span>
        </div>
      </div>
    </section>
  );
}

function ScenarioStudio() {
  const [activeScenario, setActiveScenario] = useState<ScenarioId>("reservation");
  const [isThinking, setIsThinking] = useState(false);
  const [visibleResponse, setVisibleResponse] = useState("");
  const scenario = scenarios.find((item) => item.id === activeScenario) ?? scenarios[0];

  useEffect(() => {
    setIsThinking(true);
    setVisibleResponse("");
    const timer = window.setTimeout(() => {
      setVisibleResponse(scenario.response);
      setIsThinking(false);
    }, 560);
    return () => window.clearTimeout(timer);
  }, [activeScenario, scenario.response]);

  const handleQuickReply = (next: ScenarioId) => {
    setActiveScenario(next);
  };

  return (
    <div className="studio-shell">
      <div className="studio-core">
        <div className="studio-topbar">
          <div className="studio-title">
            <span className="studio-live-dot" />
            <span>Интерактивный прототип</span>
          </div>
          <span className="studio-meta">FRONTEND / TELEGRAM UI</span>
        </div>
        <div className="studio-tabs" role="tablist" aria-label="Сценарии бота">
          {scenarios.map((item) => (
            <button
              key={item.id}
              id={`scenario-tab-${item.id}`}
              className={activeScenario === item.id ? "is-active" : ""}
              type="button"
              role="tab"
              aria-selected={activeScenario === item.id}
              aria-controls="scenario-panel"
              onClick={() => setActiveScenario(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
        <div className="telegram-window" aria-label="Предпросмотр диалога Urban Taste в Telegram">
          <div className="telegram-statusbar" aria-hidden="true">
            <span>19:42</span>
            <span className="telegram-status-icons">
              <span className="telegram-signal" />
              <span className="telegram-network">LTE</span>
              <span className="telegram-battery"><span /></span>
            </span>
          </div>
          <div className="telegram-header">
            <div className="telegram-header-main">
              <ArrowLeft size={20} weight="regular" aria-hidden="true" />
              <span className="telegram-avatar">UT</span>
              <div className="telegram-header-copy">
                <strong>
                  Urban Taste <CheckCircle className="telegram-verified" size={14} weight="fill" aria-hidden="true" />
                </strong>
                <span>{isThinking ? "печатает…" : "бот · онлайн"}</span>
              </div>
            </div>
            <div className="telegram-header-actions" aria-hidden="true">
              <Phone size={18} weight="regular" />
              <DotsThreeVertical size={20} weight="bold" />
            </div>
          </div>
          <div
            id="scenario-panel"
            className="telegram-chat"
            role="tabpanel"
            aria-live="polite"
            aria-labelledby={`scenario-tab-${activeScenario}`}
          >
            <div className="telegram-date-pill">Сегодня</div>
            <motion.div
              className="telegram-message telegram-message-outgoing"
              key={`${activeScenario}-query`}
              layout
              initial={{ opacity: 0, x: 10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.45, ease }}
              aria-label={`Сообщение клиента: ${scenario.query}`}
            >
              <span className="telegram-message-text">{scenario.query}</span>
              <span className="telegram-message-meta">
                <time dateTime="2026-09-16T19:41:00+04:00">19:41</time>
                <span className="telegram-checks" aria-label="Прочитано">
                  <Check size={12} weight="bold" aria-hidden="true" />
                  <Check size={12} weight="bold" aria-hidden="true" />
                </span>
              </span>
            </motion.div>
            <AnimatePresence mode="wait" initial={false}>
              {isThinking ? (
                <motion.div
                  className="telegram-message telegram-message-incoming telegram-typing-bubble"
                  key="loading"
                  layout
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -6 }}
                  transition={{ duration: 0.35, ease }}
                  aria-label="Urban Taste печатает"
                >
                  <span className="telegram-typing-dots" aria-hidden="true">
                    <span />
                    <span />
                    <span />
                  </span>
                </motion.div>
              ) : (
                <motion.div
                  className="telegram-message telegram-message-incoming"
                  key="response"
                  layout
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.45, ease }}
                  aria-label={`Ответ Urban Taste: ${visibleResponse}`}
                >
                  <span className="telegram-message-text">{visibleResponse}</span>
                  <span className="telegram-message-meta">
                    <time dateTime="2026-09-16T19:42:00+04:00">19:42</time>
                  </span>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
          <motion.div className="telegram-keyboard" layout role="group" aria-label="Быстрые ответы">
            {scenario.quickReplies.map((reply) => (
              <button key={reply.label} type="button" onClick={() => handleQuickReply(reply.next)}>
                {reply.label}
              </button>
            ))}
          </motion.div>
          <div className="telegram-composer" aria-label="Поле сообщения в демонстрационном чате">
            <span className="telegram-composer-action" aria-hidden="true">
              <Paperclip size={19} weight="regular" />
            </span>
            <span className="telegram-composer-placeholder">Сообщение</span>
            <span className="telegram-composer-action" aria-hidden="true">
              <Smiley size={19} weight="regular" />
            </span>
            <span className="telegram-composer-action telegram-mic" aria-hidden="true">
              <Microphone size={19} weight="regular" />
            </span>
          </div>
        </div>
        <motion.div className="studio-result" layout>
          <div>
            <span className="result-label">Что происходит дальше</span>
            <strong>{scenario.result}</strong>
          </div>
          <div className="result-tags">
            {scenario.meta.map((item) => (
              <span key={item}>{item}</span>
            ))}
          </div>
        </motion.div>
      </div>
    </div>
  );
}

function FlowSection() {
  const steps = [
    ["01", "Сообщение", "Клиент пишет обычным текстом"],
    ["02", "Квалификация", "AI определяет тип обращения"],
    ["03", "Сбор данных", "FSM ведёт по нужным полям"],
    ["04", "Передача", "Администратор получает заявку"],
  ];

  return (
    <section id="flow" className="section-shell section-block flow-section">
      <div className="section-heading split-heading">
        <div>
          <SectionLabel index="01" label="USER JOURNEY" />
          <h2>Один сценарий.<br />Четыре понятных шага.</h2>
        </div>
        <p>
          Хороший бот не прячет механику за магией. Он берёт на себя повторяемую работу и вовремя зовёт человека туда,
          где нужна ответственность.
        </p>
      </div>
      <div className="flow-layout">
        <div className="flow-steps">
          {steps.map(([number, title, text], index) => (
            <Reveal key={number} delay={index * 0.05} className="flow-step">
              <span className="flow-step-number">{number}</span>
              <div>
                <strong>{title}</strong>
                <span>{text}</span>
              </div>
              {index === steps.length - 1 ? <Check size={20} weight="regular" /> : <ArrowDownRight size={20} weight="regular" />}
            </Reveal>
          ))}
        </div>
        <Reveal className="studio-wrap" delay={0.1}>
          <ScenarioStudio />
        </Reveal>
      </div>
    </section>
  );
}

function KnowledgeVisual() {
  return (
    <div className="visual-shell visual-knowledge">
      <div className="visual-core">
        <div className="visual-topline">
          <span>AI / CONTEXT</span>
          <span className="visual-check"><Check size={14} weight="bold" /> verified</span>
        </div>
        <div className="knowledge-question">«Сколько стоит банкет?»</div>
        <div className="knowledge-divider" />
        <div className="knowledge-answer">
          <span className="answer-label">Правило ассистента</span>
          <strong>Не придумывать условия, которых нет в базе.</strong>
          <span>Передать вопрос администратору, если данных недостаточно.</span>
        </div>
        <div className="knowledge-footer">
          <span><ShieldCheck size={17} weight="regular" /> grounded response</span>
          <span>01 / 03</span>
        </div>
      </div>
    </div>
  );
}

function AdminVisual() {
  const requests = [
    ["#104", "Бронь на 4 гостей", "NEW"],
    ["#103", "Вопрос о мероприятии", "IN PROGRESS"],
    ["#102", "Бронь на завтра", "DONE"],
  ];
  return (
    <div className="visual-shell visual-admin">
      <div className="visual-core">
        <div className="visual-topline">
          <span>ADMIN / INBOX</span>
          <span className="inbox-count">3 обращения</span>
        </div>
        <div className="inbox-list">
          {requests.map(([id, title, status]) => (
            <div className="inbox-row" key={id}>
              <span className="inbox-id">{id}</span>
              <span className="inbox-title">{title}</span>
              <span className={`request-status status-${status.toLowerCase().replace(" ", "-")}`}>{status}</span>
            </div>
          ))}
        </div>
        <div className="admin-footer">
          <span><ListChecks size={17} weight="regular" /> журнал событий включён</span>
          <span><ArrowUpRight size={16} weight="regular" /></span>
        </div>
      </div>
    </div>
  );
}

function SystemSection() {
  return (
    <section id="system" className="section-shell section-block system-section">
      <div className="section-heading split-heading">
        <div>
          <SectionLabel index="02" label="PRODUCT LOGIC" />
          <h2>Не просто чат.<br />Рабочий контур бизнеса.</h2>
        </div>
        <p>
          В кейсе важен не только ответ модели. Ценность появляется, когда разговор превращается в структурированное
          обращение, которое можно обработать и закрыть.
        </p>
      </div>
      <div className="feature-stack">
        <Reveal className="feature-row feature-row-first">
          <div className="feature-copy">
            <span className="feature-number">A / 01</span>
            <h3>Ответы с опорой на факты</h3>
            <p>
              В системном контексте закреплены адрес, часы, услуги и подтверждённые позиции. Если ответа нет — бот
              честно эскалирует вопрос.
            </p>
            <div className="feature-detail"><ShieldCheck size={18} weight="regular" /> меньше уверенных ошибок</div>
          </div>
          <KnowledgeVisual />
        </Reveal>
        <Reveal className="feature-row feature-row-second" delay={0.08}>
          <AdminVisual />
          <div className="feature-copy">
            <span className="feature-number">A / 02</span>
            <h3>Очередь, а не хаос в чате</h3>
            <p>
              Владелец видит новые обращения, меняет статус, открывает историю и отвечает клиенту из админ-панели.
              Уведомления проходят через outbox с повторной доставкой.
            </p>
            <div className="feature-detail"><ChartLineUp size={18} weight="regular" /> прозрачный контроль работы</div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}

function ArchitectureSection() {
  const [activeLayer, setActiveLayer] = useState("input");
  const active = architectureLayers.find((layer) => layer.id === activeLayer) ?? architectureLayers[0];

  return (
    <section className="architecture-section">
      <div className="section-shell section-block">
        <div className="section-heading split-heading dark-heading">
          <div>
            <SectionLabel index="03" label="UNDER THE HOOD" />
            <h2>Четыре слоя,<br />один маршрут.</h2>
          </div>
          <p>
            Простая для пользователя поверхность, аккуратная инженерная цепочка под ней. Каждый слой отвечает за свою
            часть работы и не смешивает ответственность.
          </p>
        </div>
        <div className="architecture-map">
          <div className="architecture-nodes">
            {architectureLayers.map((layer, index) => {
              const Icon = layer.icon;
              return (
                <div className="architecture-node-wrap" key={layer.id}>
                  <button
                    className={`architecture-node ${activeLayer === layer.id ? "is-active" : ""}`}
                    type="button"
                    onClick={() => setActiveLayer(layer.id)}
                    aria-label={`Показать слой: ${layer.label}`}
                  >
                    <span className="architecture-node-topline"><span>{layer.number}</span><span>{layer.label}</span></span>
                    <span className="architecture-icon"><Icon size={27} weight="regular" /></span>
                    <strong>{layer.title}</strong>
                  </button>
                  {index < architectureLayers.length - 1 && <span className="architecture-connector" aria-hidden="true"><ArrowRight size={19} weight="regular" /></span>}
                </div>
              );
            })}
          </div>
          <AnimatePresence mode="wait">
            <motion.div
              className="architecture-detail"
              key={active.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.45, ease }}
            >
              <div className="detail-kicker">Слой {active.number} / {active.label}</div>
              <p>{active.text}</p>
              <span className="detail-status"><span /> работает в общей цепочке</span>
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </section>
  );
}

function FitSection() {
  const [activeFit, setActiveFit] = useState("restaurant");
  const active = fitOptions.find((item) => item.id === activeFit) ?? fitOptions[0];

  return (
    <section id="fit" className="section-shell section-block fit-section">
      <div className="section-heading split-heading">
        <div>
          <SectionLabel index="04" label="GOOD FIT" />
          <h2>Где такой<br />контур полезен.</h2>
        </div>
        <p>
          Сценарий переносится туда, где много однотипных обращений, но финальное решение всё ещё остаётся за
          специалистом или владельцем.
        </p>
      </div>
      <div className="fit-layout">
        <div className="fit-list" role="tablist" aria-label="Типы бизнеса">
          {fitOptions.map((item, index) => (
            <button
              key={item.id}
              className={`fit-tab ${activeFit === item.id ? "is-active" : ""}`}
              type="button"
              role="tab"
              aria-selected={activeFit === item.id}
              onClick={() => setActiveFit(item.id)}
            >
              <span>0{index + 1}</span>
              <strong>{item.label}</strong>
              <ArrowUpRight size={19} weight="regular" />
            </button>
          ))}
        </div>
        <AnimatePresence mode="wait">
          <motion.div
            className="fit-detail"
            key={active.id}
            initial={{ opacity: 0, x: 18 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -10 }}
            transition={{ duration: 0.5, ease }}
          >
            <div className="fit-detail-mark"><Sparkle size={22} weight="regular" /></div>
            <span className="fit-detail-note">{active.note}</span>
            <h3>{active.title}</h3>
            <p>{active.text}</p>
            <div className="fit-bottom-line">
              <span>Сценарий можно адаптировать</span>
              <ArrowDownRight size={20} weight="regular" />
            </div>
          </motion.div>
        </AnimatePresence>
      </div>
    </section>
  );
}

function HonestSection() {
  return (
    <section className="honest-section">
      <div className="section-shell honest-inner">
        <div className="honest-lead">
          <SectionLabel index="05" label="WHY IT WORKS" />
          <h2>Сильная сторона —<br /><span>правильные границы.</span></h2>
        </div>
        <div className="honest-list">
          <div className="honest-row">
            <span>01</span>
            <div><strong>Не выдумывает меню</strong><p>Публично показывает только подтверждённые факты бизнеса.</p></div>
            <ShieldCheck size={24} weight="regular" />
          </div>
          <div className="honest-row">
            <span>02</span>
            <div><strong>Не теряет контекст</strong><p>История диалога и статус обращения остаются в CRM.</p></div>
            <Database size={24} weight="regular" />
          </div>
          <div className="honest-row">
            <span>03</span>
            <div><strong>Не замыкает всё на AI</strong><p>Владелец подключается там, где нужна точность и решение.</p></div>
            <UserFocus size={24} weight="regular" />
          </div>
        </div>
      </div>
    </section>
  );
}

function BriefBuilder({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [businessId, setBusinessId] = useState("restaurant");
  const [goalId, setGoalId] = useState("reservation");
  const [copyState, setCopyState] = useState<"idle" | "copied" | "error">("idle");
  const business = fitOptions.find((item) => item.id === businessId) ?? fitOptions[0];
  const goals = [
    ["reservation", "Собирать заявки"],
    ["support", "Отвечать на вопросы"],
    ["qualification", "Квалифицировать лиды"],
  ];
  const goal = goals.find(([id]) => id === goalId)?.[1] ?? goals[0][1];
  const brief = `Нужен AI Telegram-бот для бизнеса «${business.label}». Цель: ${goal.toLowerCase()}. Нужны база знаний, сохранение истории, сценарий заявки и передача важных обращений администратору.`;

  useEffect(() => {
    if (!open) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKey);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKey);
    };
  }, [open, onClose]);

  const handleCopy = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    try {
      if (!navigator.clipboard) throw new Error("clipboard unavailable");
      await navigator.clipboard.writeText(brief);
      setCopyState("copied");
    } catch {
      setCopyState("error");
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="brief-overlay"
          role="presentation"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.35, ease }}
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) onClose();
          }}
        >
          <motion.div
            className="brief-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="brief-title"
            initial={{ opacity: 0, y: 24, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.98 }}
            transition={{ duration: 0.55, ease }}
          >
            <button className="modal-close" type="button" onClick={onClose} aria-label="Закрыть окно">
              <X size={21} weight="regular" />
            </button>
            <div className="modal-eyebrow">ДЕМО / БЫСТРЫЙ БРИФ</div>
            <h2 id="brief-title">Соберите основу<br />своего сценария.</h2>
            <p>Выберите контекст и цель — на выходе получите короткое ТЗ, с которым можно начать разговор о проекте.</p>
            <form onSubmit={handleCopy}>
              <fieldset>
                <legend>Тип бизнеса</legend>
                <div className="choice-grid">
                  {fitOptions.map((item) => (
                    <button
                      key={item.id}
                      className={businessId === item.id ? "choice is-selected" : "choice"}
                      type="button"
                      onClick={() => { setBusinessId(item.id); setCopyState("idle"); }}
                    >
                      {item.label}
                      {businessId === item.id && <Check size={15} weight="bold" />}
                    </button>
                  ))}
                </div>
              </fieldset>
              <fieldset>
                <legend>Главная задача</legend>
                <div className="choice-grid choice-grid-three">
                  {goals.map(([id, label]) => (
                    <button
                      key={id}
                      className={goalId === id ? "choice is-selected" : "choice"}
                      type="button"
                      onClick={() => { setGoalId(id); setCopyState("idle"); }}
                    >
                      {label}
                      {goalId === id && <Check size={15} weight="bold" />}
                    </button>
                  ))}
                </div>
              </fieldset>
              <div className="brief-preview">
                <span>Ваш черновик</span>
                <p>{brief}</p>
              </div>
              <button className="button button-primary modal-submit" type="submit">
                <span>{copyState === "copied" ? "Скопировано" : "Скопировать бриф"}</span>
                <span className="button-icon">{copyState === "copied" ? <Check size={17} weight="bold" /> : <Copy size={17} weight="regular" />}</span>
              </button>
              {copyState === "error" && <p className="form-error">Не удалось скопировать автоматически. Выделите текст черновика вручную.</p>}
            </form>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function ContactSection({ onOpenBrief }: { onOpenBrief: () => void }) {
  return (
    <section id="contact" className="contact-section">
      <div className="section-shell contact-inner">
        <div>
          <SectionLabel index="06" label="NEXT PROJECT" />
          <h2>Есть повторяемый<br /><span>диалог с клиентом?</span></h2>
          <p>Соберём сценарий, который не обещает лишнего и действительно снимает ручную работу.</p>
        </div>
        <div className="contact-action">
          <button className="button button-primary contact-button" type="button" onClick={onOpenBrief}>
            <span>Собрать быстрый бриф</span>
            <span className="button-icon"><ArrowUpRight size={19} weight="regular" /></span>
          </button>
          <span>без формы на 12 полей</span>
        </div>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="footer-section">
      <div className="section-shell footer-inner">
        <div className="footer-brand"><Logo /><span>AI-боты, которые понимают<br />операционную задачу.</span></div>
        <div className="footer-links">
          <a href="#flow">Сценарий</a>
          <a href="#system">Архитектура</a>
          <a href="#fit">Сферы</a>
          <a href="#contact">Обсудить проект</a>
        </div>
        <div className="footer-bottom">
          <span>Urban Taste / case study</span>
          <span>© {new Date().getFullYear()} · made with intent</span>
        </div>
      </div>
    </footer>
  );
}

export default function App() {
  const [briefOpen, setBriefOpen] = useState(false);

  return (
    <div className="site-app">
      <Nav />
      <main>
        <Hero />
        <CaseRibbon />
        <FlowSection />
        <SystemSection />
        <ArchitectureSection />
        <FitSection />
        <HonestSection />
        <ContactSection onOpenBrief={() => setBriefOpen(true)} />
      </main>
      <Footer />
      <BriefBuilder open={briefOpen} onClose={() => setBriefOpen(false)} />
    </div>
  );
}
