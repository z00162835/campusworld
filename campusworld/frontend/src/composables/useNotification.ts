/**
 * Notification composable - ElMessage wrapper
 */
import { ElMessage, ElMessageBox } from 'element-plus'

export function useNotification() {
  const success = (message: string) => ElMessage.success(message)
  const error = (message: string) => ElMessage.error(message)
  const warning = (message: string) => ElMessage.warning(message)
  const info = (message: string) => ElMessage.info(message)

  const confirm = (message: string, title = '确认') => {
    return ElMessageBox.confirm(message, title, {
      confirmButtonText: '确认',
      cancelButtonText: '取消',
      type: 'warning',
    })
  }

  return {
    success,
    error,
    warning,
    info,
    confirm,
  }
}
