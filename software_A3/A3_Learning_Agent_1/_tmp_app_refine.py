from pathlib import Path
path = Path(r"d:\软件\pycharm_professional‌\my_pythonProgram\software_A3\A3_Learning_Agent\frontend\src\App.vue")
text = path.read_text(encoding="utf-8")
insert = r'''
.app-shell {
  grid-template-columns: 240px minmax(0, 1fr);
}

.sidebar {
  gap: 10px;
  padding: 14px 10px;
  background: #f7f7f8;
}

.brand-block {
  gap: 10px;
}

.brand-mark {
  width: 34px;
  height: 34px;
  border-radius: 9px;
  background: #0d0d0d;
  font-size: 13px;
}

.brand-copy strong {
  font-weight: 600;
  font-size: 13px;
}

.brand-copy p {
  font-size: 11px;
}

.nav-item {
  min-height: 34px;
  padding: 6px 10px;
}

.nav-title {
  font-weight: 400;
  font-size: 13px;
}

.section-row strong {
  font-weight: 500;
  font-size: 13px;
}

.new-chat-button {
  height: 28px;
  padding: 0 9px;
  background: #ececf1;
  font-size: 12px;
}

.session-list {
  gap: 4px;
}

.session-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  border-radius: 8px;
  background: transparent;
}

.session-row:hover,
.session-row.active {
  background: #ececf1;
}

.session-chip {
  min-height: 36px;
  padding: 7px 8px;
  background: transparent !important;
}

.session-title {
  font-size: 12px;
  font-weight: 400;
  line-height: 1.45;
}

.session-delete {
  opacity: 0;
  margin-right: 5px;
  padding: 2px 4px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #8e8ea0;
  font-size: 11px;
  cursor: pointer;
}

.session-row:hover .session-delete,
.session-row.active .session-delete {
  opacity: 1;
}

.session-delete:hover {
  background: #ffffff;
  color: #d92d20;
}

.account-card {
  grid-template-columns: 32px minmax(0, 1fr);
  padding: 6px 0;
}

.account-avatar {
  width: 32px;
  height: 32px;
  border-radius: 9px;
  font-size: 12px;
}

.account-copy strong {
  font-weight: 500;
  font-size: 13px;
}

.logout-button {
  min-height: 30px;
  font-weight: 400;
}
'''
text = text.replace("\n@media (max-width: 980px) {", insert + "\n@media (max-width: 980px) {")
path.write_text(text, encoding="utf-8")
