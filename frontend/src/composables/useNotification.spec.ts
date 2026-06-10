import { describe, expect, it, vi } from 'vitest'
import { ElMessageBox } from 'element-plus'
import { useNotification } from './useNotification'

describe('useNotification', () => {
  it('uses i18n defaults for confirmation copy', () => {
    vi.mocked(ElMessageBox.confirm).mockResolvedValue('confirm' as never)

    const { confirm } = useNotification()
    confirm('Delete item?')

    expect(ElMessageBox.confirm).toHaveBeenCalledWith(
      'Delete item?',
      '确认',
      expect.objectContaining({
        confirmButtonText: '确认',
        cancelButtonText: '取消',
      }),
    )
  })
})
