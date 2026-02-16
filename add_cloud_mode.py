import codecs

cloud_script = '''
        <!-- Cloud Mode: Hide Write Operations -->
        <script>
            if (window.IS_CLOUD_VIEW) {
                document.addEventListener('DOMContentLoaded', () => {
                    // Hide add buttons
                    const addButtons = ['addCategoryBtn', 'addProductBtn', 'saveSettingsBtn', 'saveShiftSettingsBtn', 'saveReceiptSettingsBtn'];
                    addButtons.forEach(id => {
                        const btn = document.getElementById(id);
                        if (btn) btn.style.display = 'none';
                    });

                    // Override write functions
                    const writeFunctions = [
                        'saveCategory', 'deleteCategory', 'editCategory',
                        'saveProduct', 'deleteProduct', 'editProduct', 'toggleProduct',
                        'saveSettings', 'saveShiftSettings', 'saveReceiptSettings',
                        'handleRestoreMenu', 'handleRestoreFull', 'uploadLogo'
                    ];

                    writeFunctions.forEach(funcName => {
                        if (window[funcName]) {
                            window[funcName] = function() {
                                showNotification('هذه الميزة غير متاحة في وضع العرض السحابي', 'info');
                                return false;
                            };
                        }
                    });

                    document.body.classList.add('cloud-view');
                    console.log('[Cloud Mode] Write operations disabled');
                });
            }
        </script>

        <!-- Cloud Mode CSS -->
        <style>
            .cloud-view .category-card button,
            .cloud-view .product-card button {
                display: none !important;
            }
        </style>
'''

# Read HTML file
with codecs.open(r'c:\Users\hacker\Desktop\suzz system\cloud_backend\templates\admin\index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Find closing body tag
insert_pos = html.rfind('</body>')

if insert_pos != -1:
    # Insert cloud mode scripts before </body>
    new_html = html[:insert_pos] + cloud_script + '\n    ' + html[insert_pos:]
    
    # Write back
    with codecs.open(r'c:\Users\hacker\Desktop\suzz system\cloud_backend\templates\admin\index.html', 'w', encoding='utf-8') as f:
        f.write(new_html)
    
    print('✅ Cloud mode scripts added successfully')
else:
    print('❌ Could not find </body> tag')
