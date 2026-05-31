// ══════════════════════════════════════════════════════════════
// three-experience.js - Unified 3D WebGL Experience Engine
//
// Procedural, lightweight, and high-performance WebGL animations
// powered by Three.js and GSAP. 
// Features:
//   1. WebGL compatibility checker with CSS/SVG graceful fallback
//   2. Dynamic 3D Particle Vortex Background (reacts to scroll & mouse)
//   3. Interactive Procedural 3D AI Assistant Orb (reacts to form inputs)
//   4. Mini Assistant Orb for Chat view (reacts to thinking/streaming states)
//   5. Live Theme Synchronization (Light/Dark transitions)
// ══════════════════════════════════════════════════════════════

const ChatNCT3D = (function () {
    let bgInstance = null;
    let robotInstance = null;
    let assistantInstance = null;

    // Detect if WebGL is supported by the client browser
    function isWebGLSupported() {
        try {
            const canvas = document.createElement('canvas');
            return !!(window.WebGLRenderingContext && 
                (canvas.getContext('webgl') || canvas.getContext('experimental-webgl')));
        } catch (e) {
            return false;
        }
    }

    // Detect mobile device to apply performance limits
    const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);

    // Dynamic Color Palette synced with CSS theme tokens
    function getThemeColors() {
        const isLight = document.documentElement.getAttribute('data-theme') === 'light';
        return {
            accent: isLight ? 0x6366f1 : 0x818cf8,
            accentHover: isLight ? 0x4f46e5 : 0x6366f1,
            bgPrimary: isLight ? 0xfafbfe : 0x0a0a0f,
            glow: isLight ? 0x6366f1 : 0x818cf8,
            success: 0x10b981,
            error: 0xef4444,
            starColor: isLight ? 0x4f46e5 : 0xa5b4fc,
            fogColor: isLight ? 0xf0f1f8 : 0x0a0a0f
        };
    }

    // ══════════════════════════════════════════════════════════════
    // 1. DYNAMIC 3D PARTICLE VORTEX BACKGROUND
    // ══════════════════════════════════════════════════════════════
    class ParticleBackground {
        constructor(canvasId) {
            this.canvas = document.getElementById(canvasId);
            if (!this.canvas) return;

            this.colors = getThemeColors();
            this.scene = new THREE.Scene();
            this.scene.fog = new THREE.FogExp2(this.colors.fogColor, 0.015);

            // Camera Setup
            this.camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 100);
            this.camera.position.z = 45;

            // Renderer Setup
            this.renderer = new THREE.WebGLRenderer({
                canvas: this.canvas,
                alpha: true,
                antialias: !isMobile,
                powerPreference: "high-performance"
            });
            this.renderer.setSize(window.innerWidth, window.innerHeight);
            this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, isMobile ? 1 : 2));

            // Particle Field Configuration
            this.particleCount = isMobile ? 800 : 2500;
            this.geometry = new THREE.BufferGeometry();
            this.positions = new Float32Array(this.particleCount * 3);
            this.speeds = new Float32Array(this.particleCount);
            this.angles = new Float32Array(this.particleCount);
            this.radii = new Float32Array(this.particleCount);

            const spread = 60;
            for (let i = 0; i < this.particleCount; i++) {
                // Cylindrical/vortex positioning
                const angle = Math.random() * Math.PI * 2;
                const radius = 5 + Math.random() * spread;
                const z = (Math.random() - 0.5) * 80;

                this.positions[i * 3] = Math.cos(angle) * radius;
                this.positions[i * 3 + 1] = Math.sin(angle) * radius;
                this.positions[i * 3 + 2] = z;

                this.angles[i] = angle;
                this.radii[i] = radius;
                this.speeds[i] = 0.05 + Math.random() * 0.1;
            }

            this.geometry.setAttribute('position', new THREE.BufferAttribute(this.positions, 3));

            // Custom glowing particle texture (procedural canvas)
            const pTexture = this.createParticleTexture();

            // Material using custom shader qualities
            this.material = new THREE.PointsMaterial({
                size: isMobile ? 0.35 : 0.6,
                map: pTexture,
                transparent: true,
                opacity: 0.6,
                blending: THREE.AdditiveBlending,
                depthWrite: false,
                color: this.colors.starColor
            });

            this.points = new THREE.Points(this.geometry, this.material);
            this.scene.add(this.points);

            // Interactivity State
            this.mouseX = 0;
            this.mouseY = 0;
            this.targetMouseX = 0;
            this.targetMouseY = 0;
            this.scrollOffset = 0;
            this.warpSpeed = 0; // Dynamic scroll warp effect

            this.initEvents();
            this.animate();
        }

        createParticleTexture() {
            const canvas = document.createElement('canvas');
            canvas.width = 16;
            canvas.height = 16;
            const ctx = canvas.getContext('2d');
            const grad = ctx.createRadialGradient(8, 8, 0, 8, 8, 8);
            grad.addColorStop(0, 'rgba(255, 255, 255, 1)');
            grad.addColorStop(0.3, 'rgba(200, 210, 255, 0.8)');
            grad.addColorStop(1, 'rgba(0, 0, 0, 0)');
            ctx.fillStyle = grad;
            ctx.fillRect(0, 0, 16, 16);
            return new THREE.CanvasTexture(canvas);
        }

        initEvents() {
            window.addEventListener('resize', () => {
                this.camera.aspect = window.innerWidth / window.innerHeight;
                this.camera.updateProjectionMatrix();
                this.renderer.setSize(window.innerWidth, window.innerHeight);
                this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, isMobile ? 1 : 2));
            });

            document.addEventListener('mousemove', (e) => {
                this.targetMouseX = (e.clientX - window.innerWidth / 2) * 0.015;
                this.targetMouseY = (e.clientY - window.innerHeight / 2) * 0.015;
            });
        }

        updateScroll(progress) {
            this.scrollOffset = progress;
            // Interpolate warpSpeed for dynamic speed vortex look on scroll
            gsap.to(this, {
                warpSpeed: progress,
                duration: 0.8,
                ease: "power2.out"
            });
            // Zoom the camera forward on scroll progress
            gsap.to(this.camera.position, {
                z: 45 - progress * 35,
                duration: 1.0,
                ease: "power1.out"
            });
        }

        updateTheme() {
            this.colors = getThemeColors();
            gsap.to(this.material.color, {
                r: ((this.colors.starColor >> 16) & 255) / 255,
                g: ((this.colors.starColor >> 8) & 255) / 255,
                b: (this.colors.starColor & 255) / 255,
                duration: 0.6
            });
            gsap.to(this.scene.fog.color, {
                r: ((this.colors.fogColor >> 16) & 255) / 255,
                g: ((this.colors.fogColor >> 8) & 255) / 255,
                b: (this.colors.fogColor & 255) / 255,
                duration: 0.6
            });
        }

        animate() {
            requestAnimationFrame(() => this.animate());

            const time = Date.now() * 0.0005;

            // Ease mouse interaction
            this.mouseX += (this.targetMouseX - this.mouseX) * 0.05;
            this.mouseY += (this.targetMouseY - this.mouseY) * 0.05;

            this.scene.rotation.y = this.mouseX * 0.15 + time * 0.02;
            this.scene.rotation.x = this.mouseY * 0.15;

            // Animate particles in space
            const posAttr = this.geometry.attributes.position;
            const posArray = posAttr.array;

            // Dynamic speed increase based on warp scroll state
            const speedMultiplier = 1.0 + this.warpSpeed * 8.0;

            for (let i = 0; i < this.particleCount; i++) {
                this.angles[i] += this.speeds[i] * 0.02 * speedMultiplier;
                
                // Spiral/tunnel warp movement
                posArray[i * 3] = Math.cos(this.angles[i]) * this.radii[i];
                posArray[i * 3 + 1] = Math.sin(this.angles[i]) * this.radii[i];
                
                // Scroll warp stretches coordinate system to simulate rapid flight
                if (this.warpSpeed > 0.05) {
                    posArray[i * 3 + 2] += this.speeds[i] * 2.0 * speedMultiplier;
                    if (posArray[i * 3 + 2] > 40) {
                        posArray[i * 3 + 2] = -50;
                    }
                } else {
                    // Gentle ambient float
                    posArray[i * 3 + 2] += Math.sin(time + this.radii[i]) * 0.01;
                }
            }

            posAttr.needsUpdate = true;
            this.renderer.render(this.scene, this.camera);
        }
    }


    // ══════════════════════════════════════════════════════════════
    // 2. INTERACTIVE PROCEDURAL 3D AI ROBOT ASSISTANT ORB
    // ══════════════════════════════════════════════════════════════
    class RobotOrb {
        constructor(canvasId) {
            this.canvas = document.getElementById(canvasId);
            if (!this.canvas) return;

            this.colors = getThemeColors();
            this.scene = new THREE.Scene();

            // Camera Setup
            this.camera = new THREE.PerspectiveCamera(45, this.canvas.clientWidth / this.canvas.clientHeight, 0.1, 100);
            this.camera.position.z = 10;

            // Renderer Setup
            this.renderer = new THREE.WebGLRenderer({
                canvas: this.canvas,
                alpha: true,
                antialias: true
            });
            this.renderer.setSize(this.canvas.clientWidth, this.canvas.clientHeight);
            this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

            // Lighting System
            this.ambientLight = new THREE.AmbientLight(0xffffff, 0.4);
            this.scene.add(this.ambientLight);

            this.pointLight = new THREE.PointLight(this.colors.accent, 2, 30);
            this.pointLight.position.set(2, 3, 4);
            this.scene.add(this.pointLight);

            this.coreLight = new THREE.PointLight(this.colors.accent, 3, 10);
            this.coreLight.position.set(0, 0, 0);
            this.scene.add(this.coreLight);

            // Create Procedural Model Groups
            this.group = new THREE.Group();
            this.scene.add(this.group);

            this.buildModel();
            this.initEvents();
            this.animate();

            this.isShieldMode = false;
            this.pulseFrequency = 1.0;
            this.pulseIntensity = 1.0;
        }

        buildModel() {
            // A. Inner Energy Core (Glowing Sphere)
            const coreGeo = new THREE.SphereGeometry(1.0, 32, 32);
            this.coreMat = new THREE.MeshBasicMaterial({
                color: this.colors.accent,
                transparent: true,
                opacity: 0.85
            });
            this.coreMesh = new THREE.Mesh(coreGeo, this.coreMat);
            this.group.add(this.coreMesh);

            // B. Outer Cyber Glass Shell (Glossy Glassmorphism Effect)
            const shellGeo = new THREE.SphereGeometry(1.6, 32, 32);
            this.shellMat = new THREE.MeshPhysicalMaterial({
                color: 0xffffff,
                roughness: 0.05,
                metalness: 0.1,
                transmission: 0.85,
                opacity: 0.9,
                transparent: true,
                ior: 1.5,
                thickness: 1.2,
                specularIntensity: 1.0
            });
            this.shellMesh = new THREE.Mesh(shellGeo, this.shellMat);
            this.group.add(this.shellMesh);

            // C. Coordinate Orbiting Rings (Holographic Coordinate Grid)
            this.ringGroup = new THREE.Group();
            this.group.add(this.ringGroup);

            this.rings = [];
            const ringColors = [this.colors.accent, 0x818cf8, 0xa5b4fc];
            const ringSizes = [2.1, 2.3, 2.5];

            for (let i = 0; i < 3; i++) {
                const ringGeo = new THREE.TorusGeometry(ringSizes[i], 0.035, 8, 64);
                const ringMat = new THREE.MeshBasicMaterial({
                    color: ringColors[i],
                    transparent: true,
                    opacity: 0.45,
                    wireframe: true
                });
                const ring = new THREE.Mesh(ringGeo, ringMat);
                
                // Angle orbit ring
                ring.rotation.x = Math.random() * Math.PI;
                ring.rotation.y = Math.random() * Math.PI;
                
                this.ringGroup.add(ring);
                this.rings.push(ring);
            }

            // D. Outer Orbit Floating Digital Nodes
            this.nodeGroup = new THREE.Group();
            this.group.add(this.nodeGroup);
            this.nodes = [];

            const nodeCount = 8;
            for (let i = 0; i < nodeCount; i++) {
                const nodeGeo = new THREE.SphereGeometry(0.08, 8, 8);
                const nodeMat = new THREE.MeshBasicMaterial({
                    color: this.colors.starColor,
                    transparent: true,
                    opacity: 0.8
                });
                const node = new THREE.Mesh(nodeGeo, nodeMat);
                
                // Position randomly in sphere boundary
                const radius = 2.8 + Math.random() * 0.4;
                const phi = Math.random() * Math.PI * 2;
                const theta = Math.acos((Math.random() * 2) - 1);
                
                node.position.set(
                    radius * Math.sin(theta) * Math.cos(phi),
                    radius * Math.sin(theta) * Math.sin(phi),
                    radius * Math.cos(theta)
                );
                
                this.nodeGroup.add(node);
                this.nodes.push(node);
            }
        }

        initEvents() {
            // Container resize listener
            const observer = new ResizeObserver(() => {
                if (this.canvas.clientWidth && this.canvas.clientHeight) {
                    this.camera.aspect = this.canvas.clientWidth / this.canvas.clientHeight;
                    this.camera.updateProjectionMatrix();
                    this.renderer.setSize(this.canvas.clientWidth, this.canvas.clientHeight);
                }
            });
            observer.observe(this.canvas);
        }

        reactToTheme() {
            this.colors = getThemeColors();
            // Transition light & material colors smoothly
            gsap.to(this.coreMat.color, {
                r: ((this.colors.accent >> 16) & 255) / 255,
                g: ((this.colors.accent >> 8) & 255) / 255,
                b: (this.colors.accent & 255) / 255,
                duration: 0.6
            });
            gsap.to(this.pointLight.color, {
                r: ((this.colors.accent >> 16) & 255) / 255,
                g: ((this.colors.accent >> 8) & 255) / 255,
                b: (this.colors.accent & 255) / 255,
                duration: 0.6
            });
            this.rings.forEach(ring => {
                gsap.to(ring.material.color, {
                    r: ((this.colors.accent >> 16) & 255) / 255,
                    g: ((this.colors.accent >> 8) & 255) / 255,
                    b: (this.colors.accent & 255) / 255,
                    duration: 0.6
                });
            });
        }

        reactToHover(isHovered) {
            gsap.to(this.group.scale, {
                x: isHovered ? 1.15 : 1.0,
                y: isHovered ? 1.15 : 1.0,
                z: isHovered ? 1.15 : 1.0,
                duration: 0.4,
                ease: "power2.out"
            });
            gsap.to(this, {
                pulseFrequency: isHovered ? 2.5 : 1.0,
                pulseIntensity: isHovered ? 1.6 : 1.0,
                duration: 0.5
            });
        }

        reactToInput(inputName, value) {
            if (inputName === 'email') {
                // Focus eye direction to input box (rotate slightly left-downwards)
                gsap.to(this.group.rotation, {
                    y: -0.4,
                    x: 0.15,
                    duration: 0.5,
                    ease: "power1.out"
                });
                
                // Core pulses rapidly on typing
                gsap.killTweensOf(this.coreMat);
                this.coreMat.opacity = 1.0;
                gsap.to(this.coreMat, {
                    opacity: 0.7,
                    duration: 0.15,
                    yoyo: true,
                    repeat: 1
                });
            } else if (inputName === 'password') {
                // Security Shielding Mode: align coordinate rings horizontally
                this.isShieldMode = true;
                this.rings.forEach((ring, idx) => {
                    gsap.to(ring.rotation, {
                        x: Math.PI / 2 + (idx - 1) * 0.1,
                        y: 0,
                        z: ring.rotation.z,
                        duration: 0.6,
                        ease: "power2.out"
                    });
                });
                gsap.to(this.group.rotation, {
                    y: 0,
                    x: -0.2, // Shield face looks downwards
                    duration: 0.5
                });
            }
        }

        reactToBlur() {
            this.isShieldMode = false;
            // Ease orb position back to neutral straight view
            gsap.to(this.group.rotation, {
                x: 0,
                y: 0,
                duration: 0.6,
                ease: "power2.out"
            });
        }

        reactToSubmit() {
            gsap.to(this, {
                pulseFrequency: 4.0,
                pulseIntensity: 2.0,
                duration: 0.4
            });
        }

        reactToSuccess() {
            gsap.killTweensOf(this);
            gsap.killTweensOf(this.group.rotation);
            gsap.killTweensOf(this.coreMat);

            // A fast orbital success ring explosion
            this.coreMat.color.setHex(this.colors.success);
            this.coreLight.color.setHex(this.colors.success);

            gsap.to(this.group.scale, {
                x: 1.4, y: 1.4, z: 1.4,
                duration: 0.3,
                yoyo: true,
                repeat: 1,
                ease: "bounce.out"
            });

            gsap.to(this.group.rotation, {
                y: Math.PI * 4,
                duration: 1.0,
                ease: "power3.inOut"
            });
        }

        reactToFailure() {
            gsap.killTweensOf(this);
            // Flash red & wiggles/shakes orb horizontally to manifest failure
            this.coreMat.color.setHex(this.colors.error);
            this.coreLight.color.setHex(this.colors.error);

            const timeline = gsap.timeline();
            const originalX = this.group.position.x;
            
            timeline.to(this.group.position, { x: originalX - 0.4, duration: 0.05, ease: "rough" })
                    .to(this.group.position, { x: originalX + 0.4, duration: 0.05, ease: "rough" })
                    .to(this.group.position, { x: originalX - 0.3, duration: 0.05, ease: "rough" })
                    .to(this.group.position, { x: originalX + 0.3, duration: 0.05, ease: "rough" })
                    .to(this.group.position, { x: originalX, duration: 0.1, ease: "power2.out" });

            gsap.to(this, {
                pulseFrequency: 0.5,
                pulseIntensity: 0.4,
                duration: 1.5,
                onComplete: () => {
                    // Revert color back to accent indigo
                    gsap.to(this.coreMat.color, {
                        r: ((this.colors.accent >> 16) & 255) / 255,
                        g: ((this.colors.accent >> 8) & 255) / 255,
                        b: (this.colors.accent & 255) / 255,
                        duration: 1.0
                    });
                    gsap.to(this.coreLight.color, {
                        r: ((this.colors.accent >> 16) & 255) / 255,
                        g: ((this.colors.accent >> 8) & 255) / 255,
                        b: (this.colors.accent & 255) / 255,
                        duration: 1.0
                    });
                    this.pulseFrequency = 1.0;
                    this.pulseIntensity = 1.0;
                }
            });
        }

        animate() {
            requestAnimationFrame(() => this.animate());

            const time = Date.now() * 0.001;

            // A. Breathing Float Motion (Sine Wave bobbing)
            if (!this.group.position.x_wobble) {
                this.group.position.y = Math.sin(time * 1.5) * 0.25;
            }

            // B. Coordinate Rings Rotation (Shield alignment bypass if disabled)
            if (!this.isShieldMode) {
                this.rings[0].rotation.y = time * 0.6;
                this.rings[1].rotation.x = time * -0.4;
                this.rings[2].rotation.z = time * 0.5;
            } else {
                // Coordinate rings rotate slowly horizontally while shielding
                this.rings.forEach((ring, idx) => {
                    ring.rotation.z = time * 0.3 * (idx + 1);
                });
            }

            // C. Nodes Orbit Motion
            this.nodeGroup.rotation.y = time * 0.25;
            this.nodeGroup.rotation.x = Math.sin(time * 0.2) * 0.15;

            // D. Glow core breathing pulse
            const pulse = 0.75 + Math.sin(time * 6.0 * this.pulseFrequency) * 0.25 * this.pulseIntensity;
            this.coreMat.opacity = 0.6 * pulse;
            this.coreLight.intensity = 2.0 * pulse;

            this.renderer.render(this.scene, this.camera);
        }
    }


    // ══════════════════════════════════════════════════════════════
    // 3. COMPACT CHAT NAV-BAR ASSISTANT ORB
    // ══════════════════════════════════════════════════════════════
    class ChatAssistantOrb {
        constructor(canvasId) {
            this.canvas = document.getElementById(canvasId);
            if (!this.canvas) return;

            this.colors = getThemeColors();
            this.scene = new THREE.Scene();

            // Camera Setup
            this.camera = new THREE.PerspectiveCamera(40, 1, 0.1, 10);
            this.camera.position.z = 4.2;

            // Renderer Setup
            this.renderer = new THREE.WebGLRenderer({
                canvas: this.canvas,
                alpha: true,
                antialias: true
            });
            this.renderer.setSize(42, 42);
            this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

            // Core Light
            this.coreLight = new THREE.PointLight(this.colors.accent, 2, 5);
            this.coreLight.position.set(0, 0, 1);
            this.scene.add(this.coreLight);

            // Construct compact meshes
            this.group = new THREE.Group();
            this.scene.add(this.group);

            this.buildModel();
            this.animate();

            this.isThinking = false;
            this.pulseSpeed = 1.0;
        }

        buildModel() {
            // A. Mini core
            const coreGeo = new THREE.SphereGeometry(0.5, 16, 16);
            this.coreMat = new THREE.MeshBasicMaterial({
                color: this.colors.accent,
                transparent: true,
                opacity: 0.8
            });
            this.coreMesh = new THREE.Mesh(coreGeo, this.coreMat);
            this.group.add(this.coreMesh);

            // B. Tiny coordinate rings
            this.rings = [];
            for (let i = 0; i < 2; i++) {
                const ringGeo = new THREE.TorusGeometry(0.85 + i * 0.15, 0.02, 6, 32);
                const ringMat = new THREE.MeshBasicMaterial({
                    color: this.colors.accent,
                    transparent: true,
                    opacity: 0.35,
                    wireframe: true
                });
                const ring = new THREE.Mesh(ringGeo, ringMat);
                ring.rotation.x = Math.random() * Math.PI;
                ring.rotation.y = Math.random() * Math.PI;
                this.group.add(ring);
                this.rings.push(ring);
            }
        }

        reactToTheme() {
            this.colors = getThemeColors();
            gsap.to(this.coreMat.color, {
                r: ((this.colors.accent >> 16) & 255) / 255,
                g: ((this.colors.accent >> 8) & 255) / 255,
                b: (this.colors.accent & 255) / 255,
                duration: 0.6
            });
            this.rings.forEach(ring => {
                gsap.to(ring.material.color, {
                    r: ((this.colors.accent >> 16) & 255) / 255,
                    g: ((this.colors.accent >> 8) & 255) / 255,
                    b: (this.colors.accent & 255) / 255,
                    duration: 0.6
                });
            });
        }

        setThinking(isThinking) {
            this.isThinking = isThinking;
            gsap.to(this, {
                pulseSpeed: isThinking ? 4.0 : 1.0,
                duration: 0.4
            });
            
            // Rapid ring expansion/shrinking effect during processing
            this.rings.forEach((ring, idx) => {
                gsap.to(ring.scale, {
                    x: isThinking ? 1.25 : 1.0,
                    y: isThinking ? 1.25 : 1.0,
                    z: isThinking ? 1.25 : 1.0,
                    duration: 0.5,
                    yoyo: isThinking,
                    repeat: isThinking ? -1 : 0
                });
            });
        }

        animate() {
            requestAnimationFrame(() => this.animate());

            const time = Date.now() * 0.0015;

            // Bobbing floating
            this.group.position.y = Math.sin(time * 2.0) * 0.12;

            // Rotation
            this.rings[0].rotation.y = time * 0.8;
            this.rings[1].rotation.x = time * -0.6;

            // Breathing pulse
            const pulse = 0.7 + Math.sin(time * 4.0 * this.pulseSpeed) * 0.3;
            this.coreMat.opacity = 0.65 * pulse;
            this.coreLight.intensity = 1.5 * pulse;

            this.renderer.render(this.scene, this.camera);
        }
    }


    // ══════════════════════════════════════════════════════════════
    // UNIFIED EXPOSURE INTERFACE
    // ══════════════════════════════════════════════════════════════
    return {
        // Initialize background vortex
        initBackground: function (canvasId) {
            if (!isWebGLSupported()) return null;
            bgInstance = new ParticleBackground(canvasId);
            return bgInstance;
        },

        // Get active background vortex instance
        getBackground: function () {
            return bgInstance;
        },

        // Initialize procedural 3D assistant robot
        initRobot: function (canvasId) {
            if (!isWebGLSupported()) return null;
            robotInstance = new RobotOrb(canvasId);
            return robotInstance;
        },

        // Get active procedural robot instance
        getRobot: function () {
            return robotInstance;
        },

        // Initialize compact nav-bar assistant orb
        initAssistant: function (canvasId) {
            if (!isWebGLSupported()) return null;
            assistantInstance = new ChatAssistantOrb(canvasId);
            return assistantInstance;
        },

        // Get active compact assistant instance
        getAssistant: function () {
            return assistantInstance;
        },

        // Update active theme colors instantly across scenes
        updateTheme: function () {
            if (bgInstance) bgInstance.updateTheme();
            if (robotInstance) robotInstance.reactToTheme();
            if (assistantInstance) assistantInstance.reactToTheme();
        },

        // Check compatibility status
        isSupported: function () {
            return isWebGLSupported();
        }
    };
})();

// Hook into Light/Dark theme changes triggers to update WebGL textures
(function () {
    const originalToggle = window.toggleTheme;
    if (typeof originalToggle === 'function') {
        window.toggleTheme = function () {
            originalToggle();
            // brief delay to wait for HTML document data-theme to be updated by common.js
            setTimeout(() => ChatNCT3D.updateTheme(), 50);
        };
    }
    const originalLoginToggle = window.loginToggleTheme;
    if (typeof originalLoginToggle === 'function') {
        window.loginToggleTheme = function () {
            originalLoginToggle();
            setTimeout(() => ChatNCT3D.updateTheme(), 50);
        };
    }
})();
