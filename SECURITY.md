# Security Policy

## Supported Versions

The following versions of kube-orchestrator currently receive security updates:

| Version  | Supported          |
|----------|--------------------|
| 1.x.x    | ✅ Yes             |
| < 1.0.0  | ❌ No              |

---

## Reporting a Vulnerability

**Please do NOT report security vulnerabilities through public GitHub issues.**

If you discover a security vulnerability, please report it privately by emailing:

**abbeschrif575@gmail.com**

Include the following information in your report:

- A description of the vulnerability
- Steps to reproduce the issue
- Potential impact (what an attacker could do)
- Any suggested fix (optional)

### What to expect

| Step                          | Timeframe       |
|-------------------------------|-----------------|
| Acknowledgement of your report | Within 48 hours |
| Initial assessment             | Within 7 days   |
| Fix or mitigation              | Within 30 days  |
| Public disclosure              | After fix is released |

---

## Disclosure Policy

- We follow **Coordinated Vulnerability Disclosure (CVD)**
- We will credit you in the release notes unless you prefer to remain anonymous
- We ask that you give us a reasonable time to fix the issue before public disclosure

---

## Scope

The following are **in scope** for security reports:

- Authentication or authorization bypass in the Kubernetes client
- Credential or secret exposure (kubeconfig, API tokens)
- Arbitrary code execution via manifest rendering (Jinja2 injection)
- Dependency vulnerabilities with a CVSS score ≥ 7.0

The following are **out of scope**:

- Vulnerabilities in the Kubernetes cluster itself (report to kubernetes/kubernetes)
- Issues that require physical access to the machine
- Social engineering attacks

---

## Security Best Practices for Users

- Never commit kubeconfig files or API tokens to version control
- Use `.env.example` as a template — never commit your `.env` file
- Run the library with the least-privileged Kubernetes service account
- Keep the library updated: `pip install --upgrade kube-orchestrator`
