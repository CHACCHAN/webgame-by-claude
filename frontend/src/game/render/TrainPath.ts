import * as THREE from 'three';

const _d = new THREE.Vector3(), _e = new THREE.Vector3();

/** Path driven by the leading bogie: points every half metre, newest last, about 70 m kept. */
export class TrainPath {
  private pts: THREE.Vector3[] = [];
  private head = new THREE.Vector3();

  reset(head: THREE.Vector3, fwd: THREE.Vector3) {
    this.head.copy(head);
    this.pts = [head.clone().addScaledVector(fwd, -80), head.clone()];
  }

  advance(head: THREE.Vector3, fwd: THREE.Vector3) {
    const last = this.pts[this.pts.length - 1];
    // a respawn or a new race: start a straight train behind
    if (!last || last.distanceTo(head) > 30) return this.reset(head, fwd);
    this.head.copy(head);
    // reversing: give back the path the bogie has backed over
    while (this.pts.length > 2) {
      const a = this.pts[this.pts.length - 2], b = this.pts[this.pts.length - 1];
      if (_d.subVectors(head, b).dot(_e.subVectors(b, a)) >= 0) break;
      this.pts.pop();
    }
    if (this.pts[this.pts.length - 1].distanceTo(head) >= 0.5) this.pts.push(head.clone());
    // keep ~70 m: drop the oldest points beyond it
    let len = 0;
    for (let i = this.pts.length - 1; i > 0; i--) {
      len += this.pts[i].distanceTo(this.pts[i - 1]);
      if (len > 70 && i > 1) {
        this.pts.splice(0, i - 1);
        break;
      }
    }
  }

  /** point `d` metres back along the path from the head (extrapolated past the oldest point) */
  at(d: number, out: THREE.Vector3) {
    let prev = this.head;
    for (let i = this.pts.length - 1; i >= 0; i--) {
      const p = this.pts[i];
      const seg = prev.distanceTo(p);
      if (seg >= d && seg > 1e-6) return out.lerpVectors(prev, p, d / seg);
      d -= seg;
      prev = p;
    }
    const a = this.pts[0], b = this.pts[1] ?? this.head;
    _d.subVectors(a, b).normalize();
    return out.copy(a).addScaledVector(_d, d);
  }
}
