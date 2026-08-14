# Desktop Fallback Gate

A Clank may claim local fallback on a machine only when:

- [ ] Local runtime supported on that OS
- [ ] Required state strategy defined
- [ ] Required secrets available on machine
- [ ] Ownership/fencing supported for Level 3 (if claimed)
- [ ] Event/delivery semantics understood under fallback
- [ ] Failback procedure documented
- [ ] At least one fallback/recovery test passed
- [ ] Machine capability entry verified recently

Never advertise fake redundancy.
