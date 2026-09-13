# TASKA 20-Day Workflow

## 2026-09-13

- Goal: publish the current `taska` repository to `zbk-026/Unitree-B2Piper` and keep only the owner's author identity.
- Repository inspection: the local `main` branch had no commits; all project files were uncommitted.
- Identity selected for the initial commit: `zbk-026 <zhangbaokang123@sjtu.edu.cn>`.
- Author cleanup: removed legacy author comments and organization copyright; added the owner's author metadata to `source/taska_front/pyproject.toml` and set the license copyright to `zbk-026`.
- Documentation cleanup: replaced the clone command with the destination repository and removed the legacy model-repository username from the command, using an explicit repository placeholder instead.
- GitHub access: SSH authentication succeeded as `zbk-026`; the destination repository reported no existing refs.
- Failed attempt retained: `gh auth status` reported that the stored GitHub token is invalid. SSH will be used for the push.
- Initial commit created with both author and committer set to `zbk-026 <zhangbaokang123@sjtu.edu.cn>`.
- Push succeeded: `origin/main` now points to the repository's initial commit.
- Follow-up: commit this record update and verify the local branch is clean and synchronized with GitHub.
