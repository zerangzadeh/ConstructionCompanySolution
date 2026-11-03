### daily_reports column/source mapping

| Excel column | Authoritative source / existing transformation |
| --- | --- |
| پروژه | `'project.name'` |
| کارگاه | `'site.name'` |
| فاز | `'phase.name'` |
| تاریخ گزارش | `'reporting_date'` |
| وضعیت | `'get_status_display'` |
| آب‌وهوا | `'weather_conditions'` |
| تعداد نیرو | `'labor_count'` |
| کارهای انجام‌شده | `'work_performed'` |
| خلاصه پیشرفت | `'progress_summary'` |
| مسائل و تأخیرها | `'issues_and_delays'` |
| یادداشت ایمنی | `'safety_notes'` |
| یادداشت کیفیت | `'quality_notes'` |
| پروژه | `'report.project.name'` |
| کارگاه | `'report.site.name'` |
| فاز | `'report.phase.name'` |
| تاریخ گزارش | `'report.reporting_date'` |
| فعالیت | `'activity.name'` |
| شرح | `'description'` |
| مقدار | `'quantity'` |
| واحد | `'unit_of_measure.name'` |
| درصد پیشرفت ثبت‌شده | `'progress_percent'` |
| یادداشت | `'notes'` |
| گروه کاری | `'team_name'` |
| تعداد نیرو | `'worker_count'` |
| ساعات کارکرد | `'hours_worked'` |
| یادداشت | `'notes'` |
| تجهیز | `'equipment_name'` |
| ساعات کارکرد | `'hours_used'` |
| یادداشت | `'notes'` |
| مصالح | `lambda row: row.material.name if row.material_id else row.material_name` |
| مقدار | `'quantity'` |
| واحد | `lambda row: row.unit_of_measure.name if row.unit_of_measure_id else row.unit` |
| یادداشت | `'notes'` |
| فعالیت | `'activity.name'` |
| تاریخ وقوع | `'occurred_on'` |
| دسته | `'category'` |
| علت | `'cause'` |
| اثر | `'impact'` |
| طرف مسئول | `'responsible_party'` |
| مدت (ساعت) | `'duration_hours'` |
| وضعیت | `'get_status_display'` |

### estimates column/source mapping

| Excel column | Authoritative source / existing transformation |
| --- | --- |
| شماره برآورد | `'estimate_number'` |
| عنوان | `'title'` |
| پروژه | `'project.name'` |
| فاز | `'phase.name'` |
| قرارداد | `'contract.contract_number'` |
| بازنگری جاری | `'current_revision.revision_number'` |
| وضعیت | `'get_status_display'` |
| وضعیت بازنگری | `'current_revision.get_status_display'` |
| مبلغ کل | `'total_amount'` |
| زمان تأیید | `'approved_at'` |
| شماره برآورد | `'estimate.estimate_number'` |
| پروژه | `'estimate.project.name'` |
| بازنگری | `'revision.revision_number'` |
| شرح ردیف | `'description'` |
| واحد | `lambda row: row.unit_of_measure.name if row.unit_of_measure_id else row.unit` |
| مقدار | `'quantity'` |
| قیمت واحد | `'unit_price'` |
| مبلغ ردیف | `'line_total'` |

### timekeeping column/source mapping

| Excel column | Authoritative source / existing transformation |
| --- | --- |
| نیروی کار | `lambda row: f'{row.employee.first_name} {row.employee.last_name}'` |
| پروژه | `'project.name'` |
| کارگاه | `'site.name'` |
| نیروی کار | `lambda row: f'{row.employee.first_name} {row.employee.last_name}'` |
| شروع دوره | `'period_start'` |
| پایان دوره | `'period_end'` |
| بازنگری | `'revision'` |
| زمان اظهارشده (دقیقه) | `'declared_minutes'` |
| وضعیت | `'get_state_display'` |
| نیروی کار | `lambda row: f'{row.timesheet.employee.first_name} {row.timesheet.employee.last_name}'` |
| شروع دوره | `'timesheet.period_start'` |
| پایان دوره | `'timesheet.period_end'` |
| بازنگری | `'timesheet.revision'` |
| تاریخ | `'work_date'` |
| پروژه | `'project.name'` |
| کارگاه | `'site.name'` |
| فعالیت | `'activity.name'` |
| کارکرد (دقیقه) | `'minutes'` |
| یادداشت | `'note'` |
| تاریخ | `'work_date'` |
| ورود | `'check_in_at'` |
| خروج | `'check_out_at'` |
| وضعیت | `'get_state_display'` |
| شروع | `'starts_at'` |
| پایان | `'ends_at'` |
| دلیل | `'reason'` |
| وضعیت | `'get_state_display'` |

### equipment column/source mapping

| Excel column | Authoritative source / existing transformation |
| --- | --- |
| کد تجهیز | `'code'` |
| تجهیز | `'name'` |
| دسته | `'category'` |
| مالکیت | `'get_ownership_type_display'` |
| وضعیت | `'get_status_display'` |
| سازنده | `'manufacturer'` |
| مدل | `'model'` |
| شماره سریال | `'serial_number'` |
| شماره پلاک | `'registration_number'` |
| تاریخ تملک یا شروع اجاره | `'acquired_on'` |
| یادداشت | `'notes'` |
| کد تجهیز | `'equipment.code'` |
| تجهیز | `'equipment.name'` |
| پروژه | `'project.name'` |
| کارگاه | `'site.name'` |
| شروع تخصیص | `'start_date'` |
| پایان تخصیص | `'end_date'` |
| وضعیت | `'get_status_display'` |
| هدف تخصیص | `'purpose'` |
| یادداشت | `'notes'` |
| کد تجهیز | `'equipment.code'` |
| تجهیز | `'equipment.name'` |
| پروژه | `'deployment.project.name'` |
| کارگاه | `'deployment.site.name'` |
| شروع | `'started_at'` |
| پایان | `'ended_at'` |
| کارکرد ثبت‌شده (ساعت) | `'runtime_hours'` |
| اپراتور | `lambda row: f'{row.operator.first_name} {row.operator.last_name}' if row.operator_id else None` |
| دلیل اصلاح | `'correction_reason'` |
