from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from playwright.sync_api import Locator, Page

from .ai_backend import AIVisionBackend


@dataclass
class ResolvedElement:
    found: bool
    candidate_id: str
    confidence: float
    reason: str
    evidence: Dict[str, Any]


class AIElementResolver:
    def __init__(self, ai_backend: AIVisionBackend):
        self.ai_backend = ai_backend

    def resolve(
        self,
        page: Page,
        target: str,
        action: str,
        artifacts_dir: Path,
        artifact_prefix: str,
    ) -> ResolvedElement:
        screenshot_path = artifacts_dir / f"{artifact_prefix}-resolver.png"
        page.screenshot(path=str(screenshot_path))

        candidates = self._extract_candidates(page, mode=action)
        candidates_path = artifacts_dir / f"{artifact_prefix}-candidates.json"
        candidates_path.write_text(json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8")

        selection = self.ai_backend.select_candidate(
            image_path=str(screenshot_path),
            target=target,
            action=action,
            candidates=candidates,
        )
        evidence = {
            "engine": "ai_element_resolver",
            "target": target,
            "action": action,
            "screenshot": str(screenshot_path),
            "candidates_path": str(candidates_path),
            "confidence": selection.confidence,
            "details": selection.details,
            "raw_text": selection.raw_text,
        }
        return ResolvedElement(
            found=bool(selection.candidate_id),
            candidate_id=selection.candidate_id or "",
            confidence=selection.confidence,
            reason=selection.reason,
            evidence=evidence,
        )

    @staticmethod
    def locator_for_candidate(page: Page, candidate_id: str) -> Locator:
        return page.locator(f'[data-cu-candidate-id="{candidate_id}"]').first

    @staticmethod
    def _extract_candidates(page: Page, mode: str) -> List[Dict[str, Any]]:
        return page.evaluate(
            """(mode) => {
              const all = [...document.querySelectorAll('body *')];
              const isVisible = (el) => {
                const r = el.getBoundingClientRect();
                const s = window.getComputedStyle(el);
                return (
                  r.width > 0 &&
                  r.height > 0 &&
                  s.visibility !== 'hidden' &&
                  s.display !== 'none' &&
                  r.bottom > 0 &&
                  r.right > 0 &&
                  r.top < window.innerHeight &&
                  r.left < window.innerWidth
                );
              };
              const textOf = (value) => (value || '').replace(/\\s+/g, ' ').trim();
              const regionOf = (r) => {
                const cx = r.left + r.width / 2;
                const cy = r.top + r.height / 2;
                const horizontal = cx < window.innerWidth / 3 ? 'left' : (cx > window.innerWidth * 2 / 3 ? 'right' : 'center');
                const vertical = cy < window.innerHeight / 3 ? 'top' : (cy > window.innerHeight * 2 / 3 ? 'bottom' : 'middle');
                return vertical + '-' + horizontal;
              };
              const simpleSelector = (el) => {
                const parts = [];
                let current = el;
                let depth = 0;
                while (current && current.tagName && depth < 4) {
                  let part = current.tagName.toLowerCase();
                  if (current.id) {
                    part += '#' + current.id;
                    parts.unshift(part);
                    break;
                  }
                  const className = typeof current.className === 'string' ? current.className : '';
                  const cls = className.split(/\\s+/).filter(Boolean).slice(0, 2).join('.');
                  if (cls) {
                    part += '.' + cls;
                  }
                  parts.unshift(part);
                  current = current.parentElement;
                  depth += 1;
                }
                return parts.join(' > ');
              };
              const candidates = [];
              let idx = 0;
              for (const el of all) {
                if (!isVisible(el)) continue;
                const r = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                const tag = el.tagName.toLowerCase();
                const role = el.getAttribute('role') || '';
                const text = textOf(el.innerText || el.textContent || '').slice(0, 120);
                const aria = textOf(el.getAttribute('aria-label')).slice(0, 120);
                const alt = textOf(el.getAttribute('alt')).slice(0, 120);
                const title = textOf(el.getAttribute('title')).slice(0, 120);
                const nearby = textOf((el.parentElement && (el.parentElement.innerText || el.parentElement.textContent)) || '').slice(0, 160);
                const onclick = typeof el.onclick === 'function';
                const href = el.getAttribute('href') || '';
                const cursorPointer = style.cursor === 'pointer';
                const clickableTag = ['a', 'button', 'input', 'summary', 'label'].includes(tag);
                const semanticRole = ['button', 'link', 'tab', 'menuitem', 'option'].includes(role);
                const hasSignal = Boolean(text || aria || alt || title);
                const interactiveScore =
                  (clickableTag ? 4 : 0) +
                  (semanticRole ? 4 : 0) +
                  (onclick ? 3 : 0) +
                  (cursorPointer ? 2 : 0) +
                  (href ? 2 : 0) +
                  (hasSignal ? 1 : 0);
                const generalScore =
                  interactiveScore +
                  (hasSignal ? 2 : 0) +
                  ((r.width * r.height) > 400 ? 1 : 0);
                if (mode === 'click' && interactiveScore <= 0) continue;
                if (mode !== 'click' && generalScore <= 0) continue;
                const candidateId = `cu-${idx++}`;
                el.setAttribute('data-cu-candidate-id', candidateId);
                candidates.push({
                  candidate_id: candidateId,
                  tag,
                  role,
                  text,
                  aria,
                  alt,
                  title,
                  href: href.slice(0, 160),
                  selector_hint: simpleSelector(el),
                  region: regionOf(r),
                  bbox: {
                    x: Math.round(r.left),
                    y: Math.round(r.top),
                    width: Math.round(r.width),
                    height: Math.round(r.height)
                  },
                  interactive_score: interactiveScore,
                  general_score: generalScore,
                  cursor: style.cursor,
                  nearby_text: nearby
                });
              }
              const scoreKey = mode === 'click' ? 'interactive_score' : 'general_score';
              candidates.sort((a, b) => {
                if (b[scoreKey] !== a[scoreKey]) return b[scoreKey] - a[scoreKey];
                return (b.text || b.aria || b.alt || '').length - (a.text || a.aria || a.alt || '').length;
              });
              return candidates.slice(0, 80);
            }""",
            mode,
        )
