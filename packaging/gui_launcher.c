#define UNICODE
#define _UNICODE
#include <windows.h>
#include <shellapi.h>
#include <wchar.h>

static void dirname_inplace(wchar_t *path) {
    wchar_t *last = wcsrchr(path, L'\\');
    if (last != NULL) {
        *last = L'\0';
    }
}

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE previous, PWSTR command_line, int show) {
    wchar_t root[MAX_PATH * 4];
    wchar_t runtime[MAX_PATH * 4];
    DWORD length;
    SHELLEXECUTEINFOW info;
    DWORD exit_code = 1;
    const wchar_t *params = GetCommandLineW();

    (void)instance;
    (void)previous;
    (void)command_line;
    (void)show;

    length = GetModuleFileNameW(NULL, root, (DWORD)(sizeof(root) / sizeof(root[0])));
    if (length == 0 || length >= (DWORD)(sizeof(root) / sizeof(root[0]) - 1)) {
        MessageBoxW(NULL, L"无法确定 FileCheck 程序目录。", L"FileCheck", MB_OK | MB_ICONERROR);
        return 2;
    }
    dirname_inplace(root);

    if (_snwprintf_s(runtime, sizeof(runtime) / sizeof(runtime[0]), _TRUNCATE,
                     L"%s\\app\\FileCheck-GUI-runtime.exe", root) < 0) {
        MessageBoxW(NULL, L"FileCheck 运行时路径过长。", L"FileCheck", MB_OK | MB_ICONERROR);
        return 3;
    }

    if (GetFileAttributesW(runtime) == INVALID_FILE_ATTRIBUTES) {
        MessageBoxW(NULL,
                    L"未找到 app\\FileCheck-GUI-runtime.exe。请完整解压 FileCheck 便携包，不要只复制主程序。",
                    L"FileCheck",
                    MB_OK | MB_ICONERROR);
        return 4;
    }

    ZeroMemory(&info, sizeof(info));
    info.cbSize = sizeof(info);
    info.fMask = SEE_MASK_NOCLOSEPROCESS | SEE_MASK_FLAG_NO_UI;
    info.hwnd = NULL;
    info.lpVerb = L"open";
    info.lpFile = runtime;
    /* Passing the original command line intentionally keeps --smoke-test and
       future diagnostics visible to the Python runtime. The extra launcher
       path argument is ignored by the normal GUI entrypoint. */
    info.lpParameters = params;
    info.lpDirectory = root;
    info.nShow = SW_SHOWNORMAL;

    if (!ShellExecuteExW(&info) || info.hProcess == NULL) {
        MessageBoxW(NULL, L"无法启动 FileCheck GUI 运行时。", L"FileCheck", MB_OK | MB_ICONERROR);
        return 5;
    }

    WaitForSingleObject(info.hProcess, INFINITE);
    if (!GetExitCodeProcess(info.hProcess, &exit_code)) {
        exit_code = 6;
    }
    CloseHandle(info.hProcess);
    return (int)exit_code;
}
