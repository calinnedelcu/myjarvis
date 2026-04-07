// ═══════════════════════════════════════════════
// NEURAL NETWORK — Living Brain Engine
// ═══════════════════════════════════════════════

(function() {
    'use strict';

    let _expandedPageId = null;
    let _transitioning = false;

    const PAGE_TITLES = {
        'page-brain':    'BRAIN ANALYTICS',
        'page-briefing': 'DAILY BRIEFING',
        'page-projects': 'PROJECT TRACKER',
        'page-ide':      'CLAUDE IDE',
        'page-settings': 'SYSTEM SETTINGS',
    };

    // Toast
    window.showToast = function(message, type="info") {
        const c = document.getElementById("toast-container");
        const t = document.createElement("div");
        t.className = `toast ${type}`;
        t.textContent = message;
        c.appendChild(t);
        setTimeout(() => { t.style.animation = "slideInRight 0.3s reverse forwards"; setTimeout(() => t.remove(), 300); }, 3000);
    };

    // Clock
    function updateClock() {
        const now = new Date();
        const d = document.getElementById("header-date");
        const t = document.getElementById("header-time");
        if (d) d.textContent = now.toISOString().split("T")[0];
        if (t) t.textContent = now.toTimeString().split(" ")[0];
    }
    setInterval(updateClock, 1000);
    updateClock();

    // API
    window.apiFetch = async function(url, opts={}) {
        try { const r = await fetch(url, opts); if (!r.ok) throw new Error(`HTTP ${r.status}`); return await r.json(); }
        catch(e) { console.error("API Error:", e); return null; }
    };

    // ══════════════════════════════════════
    //  ENERGY RAYS + NEURAL WEB IN REACTOR
    // ══════════════════════════════════════

    function buildEnergyRays() {
        const g = document.getElementById('energy-rays');
        if (!g) return;
        for (let i = 0; i < 24; i++) {
            const a = (i * 15) * Math.PI / 180;
            const r1 = 55, r2 = 100 + Math.random() * 90;
            const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
            line.setAttribute('x1', 200 + r1*Math.cos(a)); line.setAttribute('y1', 200 + r1*Math.sin(a));
            line.setAttribute('x2', 200 + r2*Math.cos(a)); line.setAttribute('y2', 200 + r2*Math.sin(a));
            line.classList.add('energy-ray');
            line.style.animationDelay = (Math.random()*3)+'s';
            line.style.animationDuration = (2+Math.random()*2)+'s';
            g.appendChild(line);
        }
    }

    function buildNeuralWeb() {
        const g = document.getElementById('neural-web');
        if (!g) return;
        const pts = [];
        for (let i = 0; i < 12; i++) {
            const a = Math.random()*Math.PI*2, r = 15+Math.random()*35;
            pts.push({ x: 200+r*Math.cos(a), y: 200+r*Math.sin(a) });
        }
        for (let i = 0; i < pts.length; i++) {
            for (let j = i+1; j < pts.length; j++) {
                const d = Math.hypot(pts[i].x-pts[j].x, pts[i].y-pts[j].y);
                if (d < 40) {
                    const l = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                    l.setAttribute('x1', pts[i].x); l.setAttribute('y1', pts[i].y);
                    l.setAttribute('x2', pts[j].x); l.setAttribute('y2', pts[j].y);
                    l.setAttribute('stroke', 'rgba(0,200,232,0.3)'); l.setAttribute('stroke-width', '0.5');
                    const an = document.createElementNS('http://www.w3.org/2000/svg', 'animate');
                    an.setAttribute('attributeName', 'opacity'); an.setAttribute('values', '0.1;0.6;0.1');
                    an.setAttribute('dur', (1.5+Math.random()*2)+'s'); an.setAttribute('repeatCount', 'indefinite');
                    l.appendChild(an); g.appendChild(l);
                }
            }
            const dot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
            dot.setAttribute('cx', pts[i].x); dot.setAttribute('cy', pts[i].y);
            dot.setAttribute('r', '1'); dot.setAttribute('fill', '#00c8e8');
            const da = document.createElementNS('http://www.w3.org/2000/svg', 'animate');
            da.setAttribute('attributeName', 'r'); da.setAttribute('values', '0.5;1.5;0.5');
            da.setAttribute('dur', (1+Math.random()*2)+'s'); da.setAttribute('repeatCount', 'indefinite');
            dot.appendChild(da); g.appendChild(dot);
        }
    }

    // ══════════════════════════════════════
    //  MICRO-NODES
    // ══════════════════════════════════════

    function spawnMicroNodes() {
        const home = document.getElementById('page-home');
        if (!home) return;
        for (let i = 0; i < 25; i++) {
            const el = document.createElement('div');
            el.className = 'micro-node';
            el.style.left = (5+Math.random()*90)+'%';
            el.style.top = (5+Math.random()*90)+'%';
            el.style.width = el.style.height = (3+Math.random()*5)+'px';
            el.style.setProperty('--dx', (Math.random()*60-30)+'px');
            el.style.setProperty('--dy', (Math.random()*60-30)+'px');
            el.style.animationDuration = (15+Math.random()*25)+'s';
            el.style.animationDelay = (Math.random()*10)+'s';
            const r = Math.random();
            if (r > 0.85) { el.style.background = 'rgba(179,136,255,0.3)'; el.style.boxShadow = '0 0 6px rgba(179,136,255,0.2)'; }
            else if (r > 0.7) { el.style.background = 'rgba(0,230,118,0.3)'; el.style.boxShadow = '0 0 6px rgba(0,230,118,0.2)'; }
            home.appendChild(el);
        }
    }

    // ══════════════════════════════════════
    //  DATA ISLAND PHYSICS + DRAG
    // ══════════════════════════════════════

    // Each island: { el, homeX, homeY, x, y, phase, ampX, ampY, speedX, speedY, dragging }
    const islands = [];
    let dragTarget = null;
    let dragOffX = 0, dragOffY = 0;

    // Initial positions (% of viewport)
    const ISLAND_INIT = {
        'island-weather':   { x: 10, y: 12 },
        'island-calendar':  { x: 82, y: 10 },
        'island-email':     { x: 6,  y: 45 },
        'island-spotify':   { x: 86, y: 45 },
        'island-lights':    { x: 12, y: 78 },
        'island-telemetry': { x: 82, y: 78 },
    };

    function initIslands() {
        const home = document.getElementById('page-home');
        if (!home) return;

        document.querySelectorAll('.data-island').forEach(el => {
            const id = el.id;
            const init = ISLAND_INIT[id] || { x: 50, y: 50 };
            const vw = home.clientWidth, vh = home.clientHeight;
            const px = init.x / 100 * vw;
            const py = init.y / 100 * vh;

            const island = {
                el,
                homeX: px, homeY: py,
                x: px, y: py,
                phase: Math.random() * Math.PI * 2,
                ampX: 8 + Math.random() * 15,
                ampY: 6 + Math.random() * 12,
                speedX: 0.3 + Math.random() * 0.4,
                speedY: 0.2 + Math.random() * 0.3,
                dragging: false,
            };
            islands.push(island);

            // Position
            el.style.position = 'absolute';
            el.style.left = '0'; el.style.top = '0';
            el.style.transform = `translate(${px}px, ${py}px) translate(-50%, -50%)`;

            // Drag start
            el.addEventListener('mousedown', (e) => {
                if (e.button !== 0) return;
                e.preventDefault();
                island.dragging = true;
                el.classList.add('dragging');
                dragTarget = island;
                const rect = home.getBoundingClientRect();
                dragOffX = e.clientX - rect.left - island.x;
                dragOffY = e.clientY - rect.top - island.y;
            });
            el.addEventListener('touchstart', (e) => {
                island.dragging = true;
                el.classList.add('dragging');
                dragTarget = island;
                const rect = home.getBoundingClientRect();
                const touch = e.touches[0];
                dragOffX = touch.clientX - rect.left - island.x;
                dragOffY = touch.clientY - rect.top - island.y;
            }, { passive: true });
        });

        // Global drag move + end
        const home2 = home;
        document.addEventListener('mousemove', (e) => {
            if (!dragTarget) return;
            const rect = home2.getBoundingClientRect();
            dragTarget.x = e.clientX - rect.left - dragOffX;
            dragTarget.y = e.clientY - rect.top - dragOffY;
            dragTarget.homeX = dragTarget.x;
            dragTarget.homeY = dragTarget.y;
        });
        document.addEventListener('mouseup', () => {
            if (dragTarget) { dragTarget.dragging = false; dragTarget.el.classList.remove('dragging'); dragTarget = null; }
        });
        document.addEventListener('touchmove', (e) => {
            if (!dragTarget) return;
            const rect = home2.getBoundingClientRect();
            const t = e.touches[0];
            dragTarget.x = t.clientX - rect.left - dragOffX;
            dragTarget.y = t.clientY - rect.top - dragOffY;
            dragTarget.homeX = dragTarget.x;
            dragTarget.homeY = dragTarget.y;
        }, { passive: true });
        document.addEventListener('touchend', () => {
            if (dragTarget) { dragTarget.dragging = false; dragTarget.el.classList.remove('dragging'); dragTarget = null; }
        });
    }

    // ══════════════════════════════════════
    //  ANIMATION LOOP — float + connections
    // ══════════════════════════════════════

    // Persistent SVG connection elements (so SMIL pulses survive)
    let connectionEls = [];
    let connectionsBuilt = false;
    let loopTime = 0;

    function buildConnections() {
        const svg = document.getElementById('synapse-svg');
        if (!svg) return;
        svg.innerHTML = '';

        const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
        defs.innerHTML = `
            <filter id="sg"><feGaussianBlur stdDeviation="2.5" result="b"/>
            <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
            <filter id="sg2"><feGaussianBlur stdDeviation="1.2" result="b"/>
            <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>`;
        svg.appendChild(defs);
        connectionEls = [];

        const homeRect = document.getElementById('page-home').getBoundingClientRect();

        // Get all connectable things
        const navCircles = [];
        document.querySelectorAll('.nav-node').forEach(n => {
            const c = n.querySelector('.nav-node-circle');
            if (c) navCircles.push(c);
        });

        // Core → each nav node
        navCircles.forEach((c, i) => {
            connectionEls.push(makeLine(svg, 'rgba(0,200,232,0.15)', 1.2, '6 4'));
            connectionEls.push(makePulse(svg, 3, 'url(#sg)', 3+i*0.4, 3.5));
            connectionEls.push(makePulse(svg, 2, 'url(#sg2)', 3+i*0.4+1.8, 4));
        });

        // Core → each island
        islands.forEach((isl, i) => {
            connectionEls.push(makeLine(svg, 'rgba(0,200,232,0.08)', 0.7, '3 8'));
            connectionEls.push(makePulse(svg, 2, 'url(#sg2)', i*0.7, 3));
        });

        // Island → nearest nav nodes (cross mesh) — deterministic, visibility by distance
        islands.forEach((isl) => {
            navCircles.forEach((c, j) => {
                connectionEls.push(makeLine(svg, 'rgba(0,200,232,0.04)', 0.3, '1 14'));
            });
        });

        // Island → island (nearby pairs)
        for (let i = 0; i < islands.length; i++) {
            for (let j = i+1; j < islands.length; j++) {
                connectionEls.push(makeLine(svg, 'rgba(0,200,232,0.04)', 0.3, '2 10'));
            }
        }

        connectionsBuilt = true;
    }

    function makeLine(svg, color, width, dash) {
        const l = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        l.setAttribute('stroke', color);
        l.setAttribute('stroke-width', width);
        if (dash) l.setAttribute('stroke-dasharray', dash);
        svg.appendChild(l);
        return { type: 'line', el: l };
    }

    function makePulse(svg, r, filter, delay, dur) {
        const p = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        p.setAttribute('r', r);
        p.setAttribute('fill', '#00c8e8');
        p.setAttribute('opacity', '0');
        if (filter) p.setAttribute('filter', filter);
        svg.appendChild(p);
        return { type: 'pulse', el: p, dur, delay };
    }

    function animationLoop(ts) {
        if (_expandedPageId) { requestAnimationFrame(animationLoop); return; }

        loopTime = ts / 1000;

        const home = document.getElementById('page-home');
        if (!home) { requestAnimationFrame(animationLoop); return; }
        const homeRect = home.getBoundingClientRect();

        // Float islands
        islands.forEach(isl => {
            if (!isl.dragging) {
                isl.x = isl.homeX + Math.sin(loopTime * isl.speedX + isl.phase) * isl.ampX;
                isl.y = isl.homeY + Math.cos(loopTime * isl.speedY + isl.phase * 1.3) * isl.ampY;
            }
            isl.el.style.transform = `translate(${isl.x}px, ${isl.y}px) translate(-50%, -50%)`;
        });

        // Update connections
        if (!connectionsBuilt) { requestAnimationFrame(animationLoop); return; }

        const reactor = document.querySelector('.arc-reactor-container');
        if (!reactor) { requestAnimationFrame(animationLoop); return; }
        const rr = reactor.getBoundingClientRect();
        const cx = rr.left + rr.width/2 - homeRect.left;
        const cy = rr.top + rr.height/2 - homeRect.top;

        const navNodes = [];
        document.querySelectorAll('.nav-node').forEach(n => {
            const c = n.querySelector('.nav-node-circle');
            if (!c) return;
            const r = c.getBoundingClientRect();
            navNodes.push({ x: r.left+r.width/2-homeRect.left, y: r.top+r.height/2-homeRect.top });
        });

        let idx = 0;

        // Core → nav nodes (line + 2 pulses each)
        navNodes.forEach((n) => {
            setLinePos(connectionEls[idx++], cx, cy, n.x, n.y);
            setPulseEndpoints(connectionEls[idx++], cx, cy, n.x, n.y);
            setPulseEndpoints(connectionEls[idx++], cx, cy, n.x, n.y);
        });

        // Core → islands (line + 1 pulse each)
        islands.forEach((isl) => {
            setLinePos(connectionEls[idx++], cx, cy, isl.x, isl.y);
            setPulseEndpoints(connectionEls[idx++], cx, cy, isl.x, isl.y);
        });

        // Island → nav cross mesh (distance-based visibility)
        islands.forEach((isl) => {
            navNodes.forEach((n) => {
                const d = Math.hypot(isl.x - n.x, isl.y - n.y);
                setLinePos(connectionEls[idx], isl.x, isl.y, n.x, n.y);
                connectionEls[idx].el.style.opacity = d < 500 ? Math.max(0, 1 - d/500) : '0';
                idx++;
            });
        });

        // Island → island (distance-based visibility)
        for (let i = 0; i < islands.length; i++) {
            for (let j = i+1; j < islands.length; j++) {
                const d = Math.hypot(islands[i].x - islands[j].x, islands[i].y - islands[j].y);
                setLinePos(connectionEls[idx], islands[i].x, islands[i].y, islands[j].x, islands[j].y);
                connectionEls[idx].el.style.opacity = d < 600 ? Math.max(0, 1 - d/600) : '0';
                idx++;
            }
        }

        requestAnimationFrame(animationLoop);
    }

    function setLinePos(conn, x1, y1, x2, y2) {
        if (!conn || conn.type !== 'line') return;
        conn.el.setAttribute('x1', x1); conn.el.setAttribute('y1', y1);
        conn.el.setAttribute('x2', x2); conn.el.setAttribute('y2', y2);
    }

    function setPulseEndpoints(conn, x1, y1, x2, y2) {
        if (!conn || conn.type !== 'pulse') return;
        const p = conn.el;
        // JS-driven pulse: calculate position along line from time
        const elapsed = loopTime - conn.delay;
        if (elapsed < 0) { p.setAttribute('opacity', '0'); return; }
        const progress = (elapsed % conn.dur) / conn.dur;
        p.setAttribute('cx', x1 + (x2 - x1) * progress);
        p.setAttribute('cy', y1 + (y2 - y1) * progress);
        // Fade in at start, fade out at end
        let opacity;
        if (progress < 0.1) opacity = (progress / 0.1) * 0.9;
        else if (progress > 0.85) opacity = ((1 - progress) / 0.15) * 0.9;
        else opacity = 0.9;
        p.setAttribute('opacity', opacity);
    }

    // ══════════════════════════════════════
    //  SYNAPSE FIRING (random bright flashes)
    // ══════════════════════════════════════

    function initSynapseFiring() {
        setInterval(() => {
            if (_expandedPageId) return;
            const svg = document.getElementById('synapse-svg');
            const home = document.getElementById('page-home');
            if (!svg || !home) return;
            const hr = home.getBoundingClientRect();
            const reactor = document.querySelector('.arc-reactor-container');
            if (!reactor) return;
            const rr = reactor.getBoundingClientRect();
            const cx = rr.left+rr.width/2-hr.left, cy = rr.top+rr.height/2-hr.top;

            // Pick random target: nav node or island
            const targets = [];
            document.querySelectorAll('.nav-node .nav-node-circle').forEach(c => {
                const r = c.getBoundingClientRect();
                targets.push({ x: r.left+r.width/2-hr.left, y: r.top+r.height/2-hr.top });
            });
            islands.forEach(isl => targets.push({ x: isl.x, y: isl.y }));
            if (!targets.length) return;
            const t = targets[Math.floor(Math.random()*targets.length)];

            const flash = document.createElementNS('http://www.w3.org/2000/svg','circle');
            flash.setAttribute('r','4'); flash.setAttribute('fill','#00c8e8');
            flash.setAttribute('filter','url(#sg)');
            const dur = 0.5+Math.random()*0.4;
            ['cx','cy','opacity','r'].forEach(attr => {
                const a = document.createElementNS('http://www.w3.org/2000/svg','animate');
                a.setAttribute('attributeName', attr);
                if (attr==='cx') { a.setAttribute('from',cx); a.setAttribute('to',t.x); }
                if (attr==='cy') { a.setAttribute('from',cy); a.setAttribute('to',t.y); }
                if (attr==='opacity') { a.setAttribute('from','1'); a.setAttribute('to','0'); }
                if (attr==='r') { a.setAttribute('from','4'); a.setAttribute('to','1'); }
                a.setAttribute('dur', dur+'s'); a.setAttribute('fill','freeze');
                flash.appendChild(a);
            });
            svg.appendChild(flash);
            setTimeout(() => flash.remove(), dur*1000+100);
        }, 1800+Math.random()*2500);
    }

    // ══════════════════════════════════════
    //  MOUSE PARALLAX
    // ══════════════════════════════════════

    function initParallax() {
        const home = document.getElementById('page-home');
        if (!home) return;
        let mx = 0.5, my = 0.5;
        document.addEventListener('mousemove', e => {
            mx = e.clientX / window.innerWidth;
            my = e.clientY / window.innerHeight;
        });
        (function pLoop() {
            if (!_expandedPageId) {
                const dx = (mx-0.5)*-12, dy = (my-0.5)*-12;
                home.style.transform = `translate(${dx}px, ${dy}px)`;
            } else {
                home.style.transform = '';
            }
            requestAnimationFrame(pLoop);
        })();
    }

    // ══════════════════════════════════════
    //  NODE HOVER FOCUS
    // ══════════════════════════════════════

    function initNodeHoverFocus() {
        document.querySelectorAll('.nav-node').forEach(node => {
            node.addEventListener('mouseenter', () => {
                node.classList.add('focused');
                document.querySelectorAll('.nav-node').forEach(o => { if (o !== node) o.classList.add('dimmed-node'); });
            });
            node.addEventListener('mouseleave', () => {
                node.classList.remove('focused');
                document.querySelectorAll('.nav-node').forEach(o => o.classList.remove('dimmed-node'));
            });
        });
    }

    // ══════════════════════════════════════
    //  EXPAND / COLLAPSE
    // ══════════════════════════════════════

    function isExpanded() { return _expandedPageId !== null; }

    function expandNode(pageId, fullscreen) {
        if (_transitioning || _expandedPageId === pageId) return;
        _transitioning = true;
        const panel = document.getElementById('expanded-panel');
        const body = document.getElementById('expanded-panel-body');
        const title = document.getElementById('expanded-panel-title');
        const home = document.getElementById('page-home');
        const reactor = document.querySelector('.arc-reactor-container');
        if (!panel||!body||!home) { _transitioning=false; return; }
        const src = document.getElementById(pageId);
        if (!src) { _transitioning=false; return; }
        title.textContent = PAGE_TITLES[pageId]||pageId.replace('page-','').toUpperCase();
        panel.classList.toggle('fullscreen', !!fullscreen);
        home.classList.add('panel-expanded');
        home.style.transform = '';
        reactor.classList.add('dimmed');
        setTimeout(() => {
            body.appendChild(src); src.classList.add('active');
            panel.classList.add('visible'); _expandedPageId = pageId;
            window.dispatchEvent(new CustomEvent('page-expanded', { detail: { pageId } }));
            setTimeout(() => { _transitioning=false; window.dispatchEvent(new Event('resize')); }, 420);
        }, 280);
    }

    function collapseToHub() {
        if (_transitioning || !_expandedPageId) return;
        _transitioning = true;
        const panel = document.getElementById('expanded-panel');
        const body = document.getElementById('expanded-panel-body');
        const home = document.getElementById('page-home');
        const reactor = document.querySelector('.arc-reactor-container');
        const pc = document.querySelector('.pages-container');
        if (!panel||!body||!home||!pc) { _transitioning=false; return; }
        const src = document.getElementById(_expandedPageId);
        panel.classList.remove('visible');
        setTimeout(() => {
            if (src) { src.classList.remove('active'); pc.appendChild(src); }
            home.classList.remove('panel-expanded');
            reactor.classList.remove('dimmed');
            panel.classList.remove('fullscreen'); _expandedPageId = null;
            setTimeout(() => { _transitioning=false; }, 320);
        }, 400);
    }

    // ══════════════════════════════════════
    //  INIT
    // ══════════════════════════════════════

    document.addEventListener('DOMContentLoaded', () => {
        const homePage = document.getElementById('page-home');
        if (homePage) homePage.classList.add('active');

        buildEnergyRays();
        buildNeuralWeb();
        spawnMicroNodes();
        initIslands();

        // Node clicks
        document.querySelectorAll('.nav-node').forEach(node => {
            node.addEventListener('click', () => {
                const pid = node.getAttribute('data-page');
                if (pid === 'home-data') { if (isExpanded()) collapseToHub(); return; }
                if (isExpanded()) { collapseToHub(); setTimeout(() => expandNode(pid, node.getAttribute('data-fullscreen')==='true'), 800); }
                else expandNode(pid, node.getAttribute('data-fullscreen')==='true');
            });
        });

        document.getElementById('expanded-panel-close')?.addEventListener('click', collapseToHub);
        document.getElementById('expanded-panel')?.addEventListener('click', e => { if (e.target.id==='expanded-panel') collapseToHub(); });
        document.addEventListener('keydown', e => { if (e.key==='Escape' && isExpanded()) collapseToHub(); });

        // Build connections + start animation after layout settles
        requestAnimationFrame(() => setTimeout(() => {
            buildConnections();
            requestAnimationFrame(animationLoop);
        }, 300));

        initParallax();
        initNodeHoverFocus();
        setTimeout(initSynapseFiring, 1500);
    });

    window.neuralNav = { expandNode, collapseToHub, isExpanded };
})();
