// API Base URL (usar ruta relativa, NO localhost)
const API_BASE = '';

// Estado global
let currentTasa = 0;
let carrito = [];
let productosHistorial = [];

// ========== UTILIDADES ==========
function showToast(message, duration = 3000) {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.classList.add('show');
    setTimeout(() => {
        toast.classList.remove('show');
    }, duration);
}

function showLoading() {
    document.getElementById('loading').classList.add('show');
}

function hideLoading() {
    document.getElementById('loading').classList.remove('show');
}

async function fetchAPI(url, options = {}) {
    try {
        const response = await fetch(url, {
            headers: { 'Content-Type': 'application/json' },
            ...options
        });
        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        showToast('Error de conexión');
        return null;
    }
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ========== TASA BCV ==========
async function cargarTasa() {
    try {
        const response = await fetch('/api/tasa');
        const data = await response.json();
        currentTasa = data.bcv_usd || 0;
        const tasaElement = document.getElementById('tasa_actual');
        if (tasaElement) tasaElement.textContent = currentTasa.toFixed(2);
        return currentTasa;
    } catch (error) {
        console.error('Error cargando tasa:', error);
        return 0;
    }
}

// ========== CLIENTES ==========
async function cargarClientes() {
    const clientesData = await fetchAPI('/api/clientes');
    if (clientesData) {
        const select = document.getElementById('venta_cliente');
        const lista = document.getElementById('lista_clientes');
        
        if (select) {
            select.innerHTML = '<option value="">Seleccionar cliente</option>';
            clientesData.forEach(cliente => {
                select.innerHTML += `<option value="${cliente.id}">${escapeHtml(cliente.nombre)}</option>`;
            });
        }
        
        if (lista) {
            lista.innerHTML = clientesData.map(cliente => `
                <div class="cliente-item" data-id="${cliente.id}">
                    <div class="cliente-info">
                        <strong>${escapeHtml(cliente.nombre)}</strong>
                        <small>📞 ${cliente.telefono || 'Sin teléfono'}</small>
                    </div>
                    <div class="cliente-actions">
                        <button class="btn-icon primary" onclick="editarCliente(${cliente.id}, '${escapeHtml(cliente.nombre)}', '${cliente.telefono || ''}')">
                            <i class="material-icons">edit</i>
                        </button>
                    </div>
                </div>
            `).join('');
        }
    }
}

async function agregarCliente() {
    let nombre = document.getElementById('cliente_nombre')?.value;
    let telefono = document.getElementById('cliente_telefono')?.value;
    
    if (!nombre) {
        showToast('Ingrese el nombre del cliente');
        return;
    }
    
    if (telefono) {
        telefono = telefono.replace(/\D/g, '');
        if (telefono.length === 10) {
            telefono = '0' + telefono;
        }
    }
    
    showLoading();
    const result = await fetchAPI('/api/clientes/validar', {
        method: 'POST',
        body: JSON.stringify({ nombre, telefono })
    });
    hideLoading();
        
    if (result && result.success) {
        showToast('✅ Cliente agregado');
        document.getElementById('cliente_nombre').value = '';
        document.getElementById('cliente_telefono').value = '';
        cargarClientes();
        cargarClientesHistorial();
    } else if (result && result.cliente_existente) {
        const usarExistente = confirm(`⚠️ Ya existe un cliente con ese teléfono:\n\n${result.cliente_existente.nombre}\n\n¿Desea seleccionar este cliente?`);
        if (usarExistente) {
            const selectCliente = document.getElementById('venta_cliente');
            if (selectCliente) {
                selectCliente.value = result.cliente_existente.id;
                showToast(`Cliente seleccionado: ${result.cliente_existente.nombre}`);
            }
            document.getElementById('cliente_nombre').value = '';
            document.getElementById('cliente_telefono').value = '';
        }
    } else if (result && result.error) {
        showToast(result.error);
    }
}

async function editarCliente(id, nombreActual, telefonoActual) {
    const nuevoNombre = prompt('Ingrese el nuevo nombre:', nombreActual);
    if (!nuevoNombre) return;
    
    let nuevoTelefono = prompt('Ingrese el nuevo teléfono (formato: 0412-XXXXXXX):', telefonoActual);
    
    showLoading();
    try {
        const response = await fetch(`/api/clientes/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ nombre: nuevoNombre, telefono: nuevoTelefono })
        });
        const result = await response.json();
        if (result.success) {
            showToast('✅ Cliente actualizado');
            cargarClientes();
        } else {
            showToast(result.error);
        }
    } catch (error) {
        showToast('Error al actualizar cliente');
    } finally {
        hideLoading();
    }
}

// ========== BUSCADOR Y MODIFICACIÓN DE CLIENTES ==========
async function buscarClientePorNombre() {
    const nombre = document.getElementById('buscar_cliente_nombre')?.value;
    
    if (!nombre || nombre.length < 2) {
        document.getElementById('resultado_busqueda_cliente').style.display = 'none';
        return;
    }
    
    try {
        const response = await fetch(`/api/clientes/buscar?nombre=${encodeURIComponent(nombre)}`);
        const clientes = await response.json();
        
        const resultadosDiv = document.getElementById('resultado_busqueda_cliente');
        
        if (clientes && clientes.length > 0) {
            resultadosDiv.innerHTML = clientes.map(cliente => `
                <div class="busqueda-item" onclick="seleccionarClienteModificar(${cliente.id}, '${cliente.nombre.replace(/'/g, "\\'")}', '${cliente.telefono || ''}')">
                    <strong>${cliente.nombre}</strong>
                    <small>📞 ${cliente.telefono || 'Sin teléfono'}</small>
                </div>
            `).join('');
            resultadosDiv.style.display = 'block';
        } else {
            resultadosDiv.innerHTML = '<div class="busqueda-item">No se encontraron clientes</div>';
            resultadosDiv.style.display = 'block';
        }
    } catch (error) {
        console.error('Error buscando clientes:', error);
    }
}

function seleccionarClienteModificar(id, nombre, telefono) {
    document.getElementById('modificar_cliente_card').style.display = 'block';
    document.getElementById('modificar_cliente_id').value = id;
    document.getElementById('modificar_cliente_nombre').value = nombre;
    document.getElementById('modificar_cliente_telefono').value = telefono;
    document.getElementById('buscar_cliente_nombre').value = '';
    document.getElementById('resultado_busqueda_cliente').style.display = 'none';
    showToast(`Cliente seleccionado: ${nombre}`);
}

async function actualizarCliente() {
    const id = document.getElementById('modificar_cliente_id').value;
    const nombre = document.getElementById('modificar_cliente_nombre').value;
    const telefono = document.getElementById('modificar_cliente_telefono').value;
    
    if (!nombre) {
        showToast('Complete el nombre del cliente');
        return;
    }
    
    showLoading();
    try {
        const response = await fetch(`/api/clientes/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ nombre, telefono })
        });
        const result = await response.json();
        if (result.success) {
            showToast('✅ Cliente actualizado correctamente');
            cancelarModificarCliente();
            cargarClientes();
            cargarClientesHistorial();
        } else {
            showToast(result.error || 'Error al actualizar');
        }
    } catch (error) {
        showToast('Error de conexión');
    }
    hideLoading();
}

function cancelarModificarCliente() {
    document.getElementById('modificar_cliente_card').style.display = 'none';
    document.getElementById('modificar_cliente_id').value = '';
    document.getElementById('modificar_cliente_nombre').value = '';
    document.getElementById('modificar_cliente_telefono').value = '';
}

document.addEventListener('click', function(e) {
    const resultadosDiv = document.getElementById('resultado_busqueda_cliente');
    const inputBusqueda = document.getElementById('buscar_cliente_nombre');
    if (resultadosDiv && !inputBusqueda?.contains(e.target) && !resultadosDiv.contains(e.target)) {
        resultadosDiv.style.display = 'none';
    }
});

// ========== PRODUCTOS ==========
async function cargarProductos() {
    const productosData = await fetchAPI('/api/productos');
    if (productosData) {
        const select = document.getElementById('venta_producto');
        const lista = document.getElementById('lista_productos');
        
        if (select) {
            select.innerHTML = '<option value="">Seleccionar producto</option>';
            productosData.forEach(prod => {
                select.innerHTML += `<option value="${prod.id}" data-costo="${prod.costo}">${escapeHtml(prod.descripcion)} (Stock: ${prod.cantidad || 0})</option>`;
            });
        }
        
        if (lista) {
            lista.innerHTML = productosData.map(prod => `
                <div class="producto-item">
                    <div class="producto-info">
                        <strong>${escapeHtml(prod.descripcion)}</strong>
                        <small>💰 $${prod.costo} | 📦 Stock: ${prod.cantidad || 0}</small>
                    </div>
                    <div class="producto-actions">
                        <button class="btn-icon primary" onclick="mostrarModalReponer(${prod.id}, '${escapeHtml(prod.descripcion)}', ${prod.costo})">
                            <i class="material-icons">add_box</i>
                        </button>
                    </div>
                </div>
            `).join('');
        }
    }
}

async function agregarProducto() {
    const descripcion = document.getElementById('producto_descripcion')?.value.trim();
    const costo = parseFloat(document.getElementById('producto_costo')?.value);
    const stock = parseInt(document.getElementById('producto_stock')?.value);
    
    if (!descripcion || !costo) {
        showToast('Complete todos los campos');
        return;
    }
    
    showLoading();
    const result = await fetchAPI('/api/productos', {
        method: 'POST',
        body: JSON.stringify({ descripcion, costo, stock })
    });
    hideLoading();
    
    if (result && result.success) {
        showToast('✅ Producto agregado');
        document.getElementById('producto_descripcion').value = '';
        document.getElementById('producto_costo').value = '';
        document.getElementById('producto_stock').value = '';
        cargarProductos();
    } else if (result && result.error) {
        showToast(result.error);
    }
}

// ========== BUSCADOR Y MODIFICACIÓN DE PRODUCTOS ==========
async function buscarProductoPorNombre() {
    const nombre = document.getElementById('buscar_producto_nombre')?.value;
    
    if (!nombre || nombre.length < 2) {
        document.getElementById('resultado_busqueda_producto').style.display = 'none';
        return;
    }
    
    try {
        const response = await fetch(`/api/productos/buscar?descripcion=${encodeURIComponent(nombre)}`);
        const productos = await response.json();
        
        const resultadosDiv = document.getElementById('resultado_busqueda_producto');
        
        if (productos && productos.length > 0) {
            resultadosDiv.innerHTML = productos.map(prod => `
                <div class="busqueda-item" onclick="seleccionarProductoModificar(${prod.id}, '${prod.descripcion}', ${prod.costo}, ${prod.cantidad || 0})">
                    <strong>${prod.descripcion}</strong>
                    <small>💰 $${prod.costo} | 📦 Stock: ${prod.cantidad || 0}</small>
                </div>
            `).join('');
            resultadosDiv.style.display = 'block';
        } else {
            resultadosDiv.innerHTML = '<div class="busqueda-item">No se encontraron productos</div>';
            resultadosDiv.style.display = 'block';
        }
    } catch (error) {
        console.error('Error buscando productos:', error);
    }
}

function seleccionarProductoModificar(id, descripcion, costo, stock) {
    document.getElementById('modificar_producto_card').style.display = 'block';
    document.getElementById('modificar_producto_id').value = id;
    document.getElementById('modificar_producto_descripcion').value = descripcion;
    document.getElementById('modificar_producto_costo').value = costo;
    document.getElementById('modificar_producto_stock').value = stock;
    document.getElementById('buscar_producto_nombre').value = '';
    document.getElementById('resultado_busqueda_producto').style.display = 'none';
    showToast(`Producto seleccionado: ${descripcion}`);
}

async function actualizarProducto() {
    const id = document.getElementById('modificar_producto_id').value;
    const descripcion = document.getElementById('modificar_producto_descripcion').value;
    const costo = parseFloat(document.getElementById('modificar_producto_costo').value);
    const stock = parseInt(document.getElementById('modificar_producto_stock').value);
    
    if (!descripcion || !costo) {
        showToast('Complete los campos requeridos');
        return;
    }
    
    showLoading();
    try {
        const updateResponse = await fetch(`/api/productos/actualizar/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ descripcion, costo, stock })
        });
        const updateResult = await updateResponse.json();
        
        if (updateResult.success) {
            showToast('✅ Producto actualizado correctamente');
            cancelarModificarProducto();
            cargarProductos();
        } else {
            showToast(updateResult.error || 'Error al actualizar');
        }
    } catch (error) {
        showToast('Error de conexión');
    }
    hideLoading();
}

function cancelarModificarProducto() {
    document.getElementById('modificar_producto_card').style.display = 'none';
    document.getElementById('modificar_producto_id').value = '';
    document.getElementById('modificar_producto_descripcion').value = '';
    document.getElementById('modificar_producto_costo').value = '';
    document.getElementById('modificar_producto_stock').value = '';
}

document.addEventListener('click', function(e) {
    const resultadosDiv = document.getElementById('resultado_busqueda_producto');
    const inputBusqueda = document.getElementById('buscar_producto_nombre');
    if (resultadosDiv && !inputBusqueda?.contains(e.target) && !resultadosDiv.contains(e.target)) {
        resultadosDiv.style.display = 'none';
    }
});

// ========== CARRITO ==========
function agregarAlCarrito() {
    const productoSelect = document.getElementById('venta_producto');
    const cantidad = parseInt(document.getElementById('venta_cantidad')?.value);
    
    if (!productoSelect?.value) {
        showToast('Seleccione un producto');
        return;
    }
    
    const productoId = parseInt(productoSelect.value);
    const productoNombre = productoSelect.options[productoSelect.selectedIndex].text.split(' (')[0];
    const costoUSD = parseFloat(productoSelect.options[productoSelect.selectedIndex].dataset.costo);
    
    const existente = carrito.find(item => item.id === productoId);
    if (existente) {
        existente.cantidad += cantidad;
    } else {
        carrito.push({
            id: productoId,
            nombre: productoNombre,
            cantidad: cantidad,
            costo_usd: costoUSD
        });
    }
    
    actualizarCarrito();
    document.getElementById('venta_cantidad').value = '1';
}

function actualizarCarrito() {
    const carritoDiv = document.getElementById('carrito_items');
    const totalCarrito = document.getElementById('total_carrito');
    
    if (!carritoDiv) return;
    
    if (carrito.length === 0) {
        carritoDiv.innerHTML = '<p class="empty">Carrito vacío</p>';
        totalCarrito.textContent = '0.00';
        return;
    }
    
    let html = '';
    let total = 0;
    
    carrito.forEach((item, index) => {
        const subtotal = item.costo_usd * item.cantidad * currentTasa;
        total += subtotal;
        
        html += `
            <div class="carrito-item">
                <div class="carrito-info">
                    <strong>${escapeHtml(item.nombre)}</strong>
                    <small>$${item.costo_usd} x ${item.cantidad}</small>
                    <span>Bs ${subtotal.toFixed(2)}</span>
                </div>
                <button class="btn-icon danger" onclick="eliminarDelCarrito(${index})">
                    <i class="material-icons">delete</i>
                </button>
            </div>
        `;
    });
    
    carritoDiv.innerHTML = html;
    totalCarrito.textContent = total.toFixed(2);
}

function eliminarDelCarrito(index) {
    carrito.splice(index, 1);
    actualizarCarrito();
}

async function registrarVentaMultiple() {
    if (carrito.length === 0) {
        showToast('Agregue productos al carrito');
        return;
    }
    
    const id_cliente = document.getElementById('venta_cliente')?.value;
    const credito = document.getElementById('venta_credito')?.checked;
    
    if (!id_cliente) {
        showToast('Seleccione un cliente');
        return;
    }
    
    const productos = carrito.map(item => ({
        id_producto: item.id,
        cantidad: item.cantidad
    }));
    
    showLoading();
    const result = await fetchAPI('/api/ventas', {
        method: 'POST',
        body: JSON.stringify({ id_cliente, productos, credito })
    });
    hideLoading();
    
    if (result && result.success) {
        let mensaje = `✅ Venta registrada - Total: Bs ${result.total_bs.toFixed(2)}`;
        if (credito) mensaje += ' (Vendido a CRÉDITO)';
        showToast(mensaje);
        
        carrito = [];
        actualizarCarrito();
        document.getElementById('venta_cliente').value = '';
        document.getElementById('venta_credito').checked = false;
        
        cargarProductos();
        cargarCreditosAgrupados();
    } else if (result && result.error) {
        showToast(result.error);
    }
}

// ========== CRÉDITOS AGRUPADOS POR CLIENTE ==========
async function cargarCreditosAgrupados() {
    console.log("🔄 Cargando créditos agrupados por cliente...");
    
    try {
        const response = await fetch('/api/creditos/agrupados');
        const clientes = await response.json();
        
        const lista = document.getElementById('lista_creditos');
        
        if (!lista) {
            console.error("❌ No se encontró 'lista_creditos'");
            return;
        }
        
        if (!clientes || clientes.length === 0) {
            lista.innerHTML = '<p class="empty">✅ No hay créditos pendientes</p>';
            return;
        }
        
        let html = '';
        
        for (const cliente of clientes) {
            let totalDeudaCliente = 0;
            for (const deuda of cliente.deudas) {
                const totalUsd = deuda.total / deuda.tasa;
                totalDeudaCliente += totalUsd * currentTasa;
            }
            
            html += `
                <div class="cliente-credito-card" data-cliente-id="${cliente.cliente_id}">
                    <div class="cliente-header" onclick="toggleClienteDeudas(this)">
                        <div class="cliente-info">
                            <i class="material-icons">account_circle</i>
                            <div>
                                <strong>${escapeHtml(cliente.cliente_nombre)}</strong>
                                <small>${cliente.cliente_telefono || 'Sin teléfono'}</small>
                            </div>
                        </div>
                        <div class="cliente-total">
                            <span class="total-label">Total adeudado:</span>
                            <span class="total-amount">Bs ${totalDeudaCliente.toFixed(2)}</span>
                        </div>
                        <div class="cliente-actions">
                            <button class="btn-reporte-global" onclick="event.stopPropagation(); verReporteGlobalCliente(${cliente.cliente_id}, '${escapeHtml(cliente.cliente_nombre)}')">
                                <i class="material-icons">description</i> Reporte
                            </button>
                            <button class="btn-pago-global" onclick="event.stopPropagation(); cancelarGlobal(${cliente.cliente_id}, '${escapeHtml(cliente.cliente_nombre)}')">
                                <i class="material-icons">payment</i> Cancelar Todo
                            </button>
                            <i class="material-icons expand-icon">expand_more</i>
                        </div>
                    </div>
                    <div class="cliente-deudas" style="display: none;">
                        ${cliente.deudas.map(deuda => {
                            const totalUsd = deuda.total / deuda.tasa;
                            const totalActualizado = totalUsd * currentTasa;
                            const fechaVenta = deuda.fecha_venta.split(' ')[0];
                            
                            return `
                                <div class="deuda-item" data-venta-id="${deuda.id_venta}">
                                    <div class="deuda-fecha">📅 ${fechaVenta}</div>
                                    <div class="deuda-productos">📦 ${deuda.productos.map(p => `${escapeHtml(p.descripcion)} x${p.cantidad}`).join(', ')}</div>
                                    <div class="deuda-montos">
                                        <span>Original: Bs ${deuda.total.toFixed(2)}</span>
                                        <span>Al pagar hoy: Bs ${totalActualizado.toFixed(2)}</span>
                                    </div>
                                    <div class="deuda-actions">
                                        <button class="btn-pagar-individual" onclick="pagarCreditoIndividual(${deuda.id_venta})">
                                            <i class="material-icons">attach_money</i> Pagar
                                        </button>
                                        <button class="btn-ver-recibo" onclick="verRecibo(${deuda.id_venta})">
                                            <i class="material-icons">receipt</i> Recibo
                                        </button>
                                    </div>
                                </div>
                            `;
                        }).join('')}
                    </div>
                </div>
            `;
        }
        
        lista.innerHTML = html;
        console.log("✅ Créditos agrupados mostrados");
        
    } catch (error) {
        console.error("❌ Error cargando créditos agrupados:", error);
        const lista = document.getElementById('lista_creditos');
        if (lista) lista.innerHTML = '<p class="empty" style="color:red;">Error al cargar créditos</p>';
    }
}

function toggleClienteDeudas(headerElement) {
    const card = headerElement.closest('.cliente-credito-card');
    const deudasDiv = card.querySelector('.cliente-deudas');
    const expandIcon = headerElement.querySelector('.expand-icon');
    
    if (deudasDiv.style.display === 'none') {
        deudasDiv.style.display = 'block';
        expandIcon.textContent = 'expand_less';
    } else {
        deudasDiv.style.display = 'none';
        expandIcon.textContent = 'expand_more';
    }
}

async function verRecibo(id_venta) {
    showLoading();
    try {
        const response = await fetch(`/api/ventas/recibo/${id_venta}`);
        if (response.ok) {
            const blob = await response.blob();
            const nombreArchivo = `recibo_venta_${id_venta}_${new Date().toISOString().slice(0,19).replace(/:/g, '-')}.png`;
            abrirReciboEnModal(blob, nombreArchivo);
        } else {
            showToast('Error al cargar el recibo');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Error al cargar el recibo');
    } finally {
        hideLoading();
    }
}

async function verReporteGlobalCliente(clienteId, clienteNombre) {
    showLoading();
    try {
        const response = await fetch(`/api/creditos/reporte_cliente_pdf/${clienteId}`);
        if (response.ok) {
            const blob = await response.blob();
            const nombreArchivo = `reporte_${clienteNombre.replace(/\s/g, '_')}_${new Date().toISOString().slice(0,19).replace(/:/g, '-')}.png`;
            abrirReciboEnModal(blob, nombreArchivo);
            showToast(`📊 Reporte de ${clienteNombre} cargado`);
        } else {
            showToast('Error al generar el reporte');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Error al generar el reporte');
    } finally {
        hideLoading();
    }
}

async function cancelarGlobal(clienteId, clienteNombre) {
    if (!currentTasa || currentTasa <= 0) {
        showToast('No se puede obtener la tasa actual');
        return;
    }
    
    const confirmado = confirm(`⚠️ ¿Está seguro de CANCELAR TODAS las deudas de ${clienteNombre}?\n\nEsta acción generará un recibo único con todas las deudas canceladas.`);
    
    if (!confirmado) return;
    
    showLoading();
    
    try {
        const response = await fetch('/api/creditos/cancelar_global', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                cliente_id: clienteId,
                tasa_actual: currentTasa
            })
        });
        
        if (response.ok) {
            const blob = await response.blob();
            const nombreArchivo = `cancelacion_global_${clienteNombre.replace(/\s/g, '_')}_${new Date().toISOString().slice(0,19).replace(/:/g, '-')}.png`;
            abrirReciboEnModal(blob, nombreArchivo);
            showToast(`✅ Cancelación global completada para ${clienteNombre}`);
            setTimeout(() => {
                cargarCreditosAgrupados();
                cargarReportes('semanal');
            }, 1000);
        } else {
            const error = await response.json();
            showToast(error.error || 'Error al procesar la cancelación');
        }
    } catch (error) {
        console.error('Error en cancelación global:', error);
        showToast('Error al procesar la cancelación global');
    } finally {
        hideLoading();
    }
}

async function pagarCreditoIndividual(idVenta) {
    const opcion = confirm(`💰 PAGO DE CRÉDITO\n\n¿Desea pagar el total actualizado?\n\n✓ Aceptar = Pago COMPLETO\n✓ Cancelar = Pago PARCIAL`);
    
    let montoPagar = 0;
    let observacion = '';
    
    if (opcion) {
        montoPagar = 0;
        observacion = 'Pago completo';
    } else {
        const monto = prompt(`💰 PAGO PARCIAL\n\nIngrese el monto a pagar (Bs):`);
        if (!monto || parseFloat(monto) <= 0) {
            showToast('Pago cancelado');
            return;
        }
        montoPagar = parseFloat(monto);
        observacion = prompt('Observación (opcional):', 'Pago parcial') || 'Pago parcial';
    }
    
    showLoading();
    
    try {
        const response = await fetch('/api/creditos/pagar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                id_venta: idVenta,
                monto: montoPagar,
                observacion: observacion,
                tasa_actual: currentTasa
            })
        });
        
        if (response.ok) {
            const blob = await response.blob();
            const nombreArchivo = `recibo_pago_${idVenta}_${new Date().toISOString().slice(0,19).replace(/:/g, '-')}.png`;
            abrirReciboEnModal(blob, nombreArchivo);
            showToast(`✅ Pago registrado exitosamente`);
            cargarCreditosAgrupados();
            cargarReportes('semanal');
        } else {
            const error = await response.json();
            showToast(error.error || 'Error al registrar el pago');
        }
    } catch (error) {
        console.error('Error en pago:', error);
        showToast('Error al procesar el pago');
    } finally {
        hideLoading();
    }
}

async function cargarCreditos() {
    await cargarCreditosAgrupados();
}

function mostrarOpcionesPago(id_venta, nombre, saldo_pendiente, total_actualizado) {
    pagarCreditoIndividual(id_venta);
}

async function pagarCreditoCompleto(id_venta) {
    await pagarCreditoIndividual(id_venta);
}

async function pagarCreditoParcial(id_venta, monto) {
    showToast('Usa el botón Pagar en la lista de créditos');
}

async function enviarRecordatorios() {
    showLoading();
    const result = await fetchAPI('/api/creditos/recordatorios', { method: 'POST' });
    hideLoading();
    if (result) showToast(`📱 Recordatorios enviados`);
}

// ========== HISTORIAL ==========
async function cargarClientesHistorial() {
    try {
        const response = await fetch('/api/clientes');
        const clientes = await response.json();
        const select = document.getElementById('historial_cliente');
        if (!select) return;
        
        if (clientes && clientes.length > 0) {
            select.innerHTML = '<option value="">Seleccionar cliente</option>';
            clientes.forEach(cliente => {
                select.innerHTML += `<option value="${cliente.id}">${escapeHtml(cliente.nombre)}</option>`;
            });
        } else {
            select.innerHTML = '<option value="">No hay clientes registrados</option>';
        }
    } catch (error) {
        console.error("Error cargando clientes:", error);
    }
}

async function cargarProductosHistorial() {
    try {
        const response = await fetch('/api/productos');
        const productos = await response.json();
        const select = document.getElementById('historial_producto');
        if (!select) return;
        
        if (productos && productos.length > 0) {
            select.innerHTML = '<option value="">Seleccionar producto</option>';
            productos.forEach(prod => {
                select.innerHTML += `<option value="${prod.id}" data-costo="${prod.costo}">${escapeHtml(prod.descripcion)} ($${prod.costo})</option>`;
            });
        } else {
            select.innerHTML = '<option value="">No hay productos registrados</option>';
        }
    } catch (error) {
        console.error("Error cargando productos:", error);
    }
}

function calcularPreviewHistorial() {
    const productoSelect = document.getElementById('historial_producto');
    const cantidad = parseInt(document.getElementById('historial_cantidad').value) || 1;
    const tasa = parseFloat(document.getElementById('historial_tasa').value) || 0;
    const clienteSelect = document.getElementById('historial_cliente');
    
    if (clienteSelect && clienteSelect.value) {
        document.getElementById('preview_cliente').textContent = clienteSelect.options[clienteSelect.selectedIndex].text;
    }
    
    if (productoSelect && productoSelect.value && tasa > 0) {
        const costoUSD = parseFloat(productoSelect.options[productoSelect.selectedIndex].dataset.costo);
        const totalUSD = costoUSD * cantidad;
        const totalBS = totalUSD * tasa;
        
        document.getElementById('preview_usd').textContent = totalUSD.toFixed(2);
        document.getElementById('preview_bs').textContent = totalBS.toFixed(2);
        document.getElementById('preview_tasa').textContent = tasa.toFixed(2);
        document.getElementById('preview_producto').textContent = productoSelect.options[productoSelect.selectedIndex].text.split(' (')[0];
        document.getElementById('preview_cantidad').textContent = cantidad;
        document.getElementById('historial_preview').style.display = 'block';
    } else {
        document.getElementById('historial_preview').style.display = 'none';
    }
}

async function agregarProductoHistorial() {
    const productoSelect = document.getElementById('historial_producto');
    const cantidad = parseInt(document.getElementById('historial_cantidad').value);
    const tasa = parseFloat(document.getElementById('historial_tasa').value);
    
    if (!productoSelect.value) {
        showToast('Seleccione un producto');
        return;
    }
    
    if (tasa <= 0) {
        showToast('Ingrese la tasa BCV');
        return;
    }
    
    const id_producto = parseInt(productoSelect.value);
    const descripcion = productoSelect.options[productoSelect.selectedIndex].text.split(' (')[0];
    const costo_usd = parseFloat(productoSelect.options[productoSelect.selectedIndex].dataset.costo);
    const subtotal = costo_usd * cantidad * tasa;
    
    productosHistorial.push({
        id_producto: id_producto,
        descripcion: descripcion,
        cantidad: cantidad,
        subtotal: subtotal,
        tasa: tasa
    });
    
    actualizarListaHistorial();
    document.getElementById('historial_producto').value = '';
    document.getElementById('historial_cantidad').value = '1';
    document.getElementById('historial_tasa').value = '';
    document.getElementById('historial_preview').style.display = 'none';
    showToast('Producto agregado al carrito');
}

function actualizarListaHistorial() {
    const container = document.getElementById('lista_productos_historial');
    if (!container) return;
    
    if (productosHistorial.length === 0) {
        container.innerHTML = '<div style="text-align:center; color:#999;">No hay productos agregados</div>';
        return;
    }
    
    let html = '';
    let total = 0;
    
    productosHistorial.forEach((item, index) => {
        total += item.subtotal;
        html += `
            <div class="carrito-item">
                <div class="carrito-info">
                    <strong>${escapeHtml(item.descripcion)}</strong>
                    <small>x${item.cantidad}</small>
                    <span>Bs ${item.subtotal.toFixed(2)}</span>
                </div>
                <button class="btn-icon danger" onclick="eliminarProductoHistorial(${index})">
                    <i class="material-icons">delete</i>
                </button>
            </div>
        `;
    });
    
    html += `<div class="carrito-total"><strong>Total: Bs ${total.toFixed(2)}</strong></div>`;
    container.innerHTML = html;
}

function eliminarProductoHistorial(index) {
    productosHistorial.splice(index, 1);
    actualizarListaHistorial();
}

async function guardarVentaHistorica() {
    if (productosHistorial.length === 0) {
        showToast('Agregue productos al carrito');
        return;
    }
    
    const id_cliente = document.getElementById('historial_cliente').value;
    const fecha = document.getElementById('historial_fecha').value;
    
    if (!id_cliente) {
        showToast('Seleccione un cliente');
        return;
    }
    
    if (!fecha) {
        showToast('Ingrese la fecha de compra');
        return;
    }
    
    const tasaVenta = productosHistorial[0].tasa;
    const productos = productosHistorial.map(item => ({
        id_producto: item.id_producto,
        cantidad: item.cantidad
    }));
    
    showLoading();
    const result = await fetchAPI('/api/ventas', {
        method: 'POST',
        body: JSON.stringify({ 
            id_cliente: parseInt(id_cliente), 
            productos: productos, 
            credito: true 
        })
    });
    
    if (result && result.success) {
        await fetch(`/api/ventas/actualizar-fecha/${result.id_venta}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ fecha: fecha, tasa: tasaVenta })
        });
        
        showToast('✅ Venta histórica registrada');
        productosHistorial = [];
        actualizarListaHistorial();
        document.getElementById('historial_cliente').value = '';
        document.getElementById('historial_fecha').value = '';
        cargarCreditosAgrupados();
    } else {
        showToast(result?.error || 'Error al registrar venta');
    }
    hideLoading();
}

// ========== REPORTES ==========
async function cargarReportes(tipo) {
    showLoading();
    let data = await fetchAPI(`/api/reportes/ventas?periodo=${tipo}`);
    hideLoading();
    
    const container = document.getElementById('reporte_resultados');
    if (!container) return;
    
    if (!data || data.length === 0) {
        container.innerHTML = '<p class="empty">📊 No hay datos disponibles</p>';
        return;
    }
    
    if (tipo === 'productos') {
        container.innerHTML = `
            <div class="reporte-header">
                <div class="reporte-item header">
                    <strong>Producto</strong>
                    <strong>Unidades</strong>
                    <strong>Total Bs</strong>
                </div>
                ${data.map(p => `
                    <div class="reporte-item">
                        <span><strong>${escapeHtml(p.producto || 'Producto')}</strong></span>
                        <span>${p.unidades_vendidas || 0}</span>
                        <span class="total-text">Bs ${(p.total_bs || 0).toFixed(2)}</span>
                    </div>
                `).join('')}
            </div>
        `;
    } else {
        container.innerHTML = `
            <div class="reporte-header">
                <div class="reporte-item header">
                    <strong>Período</strong>
                    <strong>Ventas</strong>
                    <strong>Total Bs</strong>
                </div>
                ${data.map(r => `
                    <div class="reporte-item">
                        <span>${r.periodo || 'Sin fecha'}</span>
                        <span>${r.total_ventas || 0}</span>
                        <span class="total-text">Bs ${(r.total_bs || 0).toFixed(2)}</span>
                    </div>
                `).join('')}
            </div>
        `;
    }
}
//== CARGAR REPORTES CON FILTROS ==
async function cargarReportesConFiltros() {
    const tipo = document.getElementById('reporte_tipo').value;
    const filtroVenta = document.getElementById('tipo_venta').value;
    let fechaInicio = document.getElementById('fecha_inicio').value;
    let fechaFin = document.getElementById('fecha_fin').value;
    
    if (!fechaInicio || !fechaFin) {
        showToast('Seleccione ambas fechas');
        return;
    }
    
    const fechaInicioMostrar = new Date(fechaInicio).toLocaleDateString();
    const fechaFinMostrar = new Date(fechaFin).toLocaleDateString();
    
    showLoading();
    
    try {
        const response = await fetch('/api/reportes/rango', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                fecha_inicio: fechaInicio,
                fecha_fin: fechaFin,
                tipo: tipo,
                filtro_venta: filtroVenta
            })
        });
        const result = await response.json();
        hideLoading();
        
        const container = document.getElementById('reporte_resultados');
        
        if (!result.success) {
            container.innerHTML = `<p class="empty">❌ Error: ${result.error}</p>`;
            return;
        }
        
        if (!result.data || result.data.length === 0) {
            container.innerHTML = '<p class="empty">📊 No hay datos en este rango de fechas</p>';
            return;
        }
        
        let html = `
            <div class="reporte-resumen">
                <h4>📅 ${fechaInicioMostrar} - ${fechaFinMostrar}</h4>
                <div class="reporte-totales">
                    <div class="reporte-total-card contado">
                        <div class="label">💰 Venta al Contado</div>
                        <div class="value">Bs ${result.totales.contado.toFixed(2)}</div>
                    </div>
                    <div class="reporte-total-card credito-pendiente">
                        <div class="label">⚠️ Crédito Pendiente</div>
                        <div class="value">Bs ${result.totales.credito_pendiente.toFixed(2)}</div>
                    </div>
                    <div class="reporte-total-card credito-cancelado">
                        <div class="label">✅ Crédito Cancelado</div>
                        <div class="value">Bs ${result.totales.credito_cancelado.toFixed(2)}</div>
                    </div>
                    <div class="reporte-total-card total">
                        <div class="label">🎯 Total General</div>
                        <div class="value">Bs ${result.totales.general.toFixed(2)}</div>
                    </div>
                </div>
            </div>
        `;
        
        // Guardar datos para el gráfico
        window.ultimosDatosGrafico = {
            data: result.data,
            tipo: tipo
        };
        
        if (tipo === 'dia') {
            const dataOrdenada = [...result.data].sort((a, b) => {
                const fechaA = a.periodo.split('/').reverse().join('-');
                const fechaB = b.periodo.split('/').reverse().join('-');
                return fechaA.localeCompare(fechaB);
            });
            
            html += `<div class="reporte-header">
                        <strong>Período</strong>
                        <strong>Cantidad</strong>
                        <strong>Contado (Bs)</strong>
                        <strong>Crédito Pend (Bs)</strong>
                        <strong>Crédito Cancel (Bs)</strong>
                        <strong>Total (Bs)</strong>
                    </div>`;
            
            for (const item of dataOrdenada) {
                const periodo = item.periodo && item.periodo !== 'null' ? item.periodo : 'Sin fecha';
                html += `
                    <div class="reporte-fila">
                        <span class="reporte-periodo">${periodo}</span>
                        <span>${item.ventas || 0}</span>
                        <span class="success-text">Bs ${(item.contado || 0).toFixed(2)}</span>
                        <span class="warning-text">Bs ${(item.credito_pendiente || 0).toFixed(2)}</span>
                        <span class="info-text">Bs ${(item.credito_cancelado || 0).toFixed(2)}</span>
                        <span class="total-text">Bs ${(item.total || 0).toFixed(2)}</span>
                    </div>
                `;
            }
        } else if (tipo === 'productos') {
            html += `<div class="reporte-header">
                        <strong>Producto</strong>
                        <strong>Cantidad</strong>
                        <strong>Contado (Bs)</strong>
                        <strong>Crédito Pend (Bs)</strong>
                        <strong>Crédito Cancel (Bs)</strong>
                        <strong>Total (Bs)</strong>
                    </div>`;
            
            for (const item of result.data) {
                const producto = item.producto || 'Producto';
                const cantidad = item.unidades_vendidas || 0;
                html += `
                    <div class="reporte-fila">
                        <span class="reporte-periodo">${producto}</span>
                        <span>${cantidad}</span>
                        <span class="success-text">Bs ${(item.total_contado || 0).toFixed(2)}</span>
                        <span class="warning-text">Bs ${(item.total_credito_pendiente || 0).toFixed(2)}</span>
                        <span class="info-text">Bs ${(item.total_credito_cancelado || 0).toFixed(2)}</span>
                        <span class="total-text">Bs ${(item.total_bs || 0).toFixed(2)}</span>
                    </div>
                `;
            }
        } else {
            html += `<div class="reporte-header">
                        <strong>Período</strong>
                        <strong>Cantidad</strong>
                        <strong>Contado (Bs)</strong>
                        <strong>Crédito Pend (Bs)</strong>
                        <strong>Crédito Cancel (Bs)</strong>
                        <strong>Total (Bs)</strong>
                    </div>`;
            
            for (const item of result.data) {
                const periodo = item.periodo && item.periodo !== 'null' ? item.periodo : 'Sin fecha';
                html += `
                    <div class="reporte-fila">
                        <span class="reporte-periodo">${periodo}</span>
                        <span>${item.ventas || 0}</span>
                        <span class="success-text">Bs ${(item.contado || 0).toFixed(2)}</span>
                        <span class="warning-text">Bs ${(item.credito_pendiente || 0).toFixed(2)}</span>
                        <span class="info-text">Bs ${(item.credito_cancelado || 0).toFixed(2)}</span>
                        <span class="total-text">Bs ${(item.total || 0).toFixed(2)}</span>
                    </div>
                `;
            }
        }
        
        container.innerHTML = html;
        
        // SOLO SI ES TIPO PRODUCTOS, mostrar el gráfico
        if (tipo === 'productos') {
            mostrarGraficoConDatos(result.data);
        } else {
            // Eliminar cualquier gráfico existente
            const graficoExistente = document.querySelector('.grafico-tabla');
            if (graficoExistente) graficoExistente.remove();
        }
        
    } catch (error) {
        hideLoading();
        console.error('Error:', error);
        document.getElementById('reporte_resultados').innerHTML = '<p class="empty">❌ Error al cargar reporte</p>';
    }
}

function mostrarGraficoConDatos(data) {
    // Eliminar gráfico anterior si existe
    const graficoExistente = document.querySelector('.grafico-tabla');
    if (graficoExistente) graficoExistente.remove();
    
    const productos = [...data].sort((a, b) => (b.unidades_vendidas || 0) - (a.unidades_vendidas || 0));
    
    let html = `
        <div class="grafico-tabla" style="background: white; border-radius: 12px; padding: 16px; margin-top: 20px;">
            <h4 style="color: #1976D2; margin-bottom: 16px;">📊 Productos más vendidos</h4>
            <div style="overflow-x: auto;">
                <table style="width: 100%; border-collapse: collapse;">
                    <thead>
                        <tr style="background: #1976D2; color: white;">
                            <th style="padding: 12px; text-align: left;">Producto</th>
                            <th style="padding: 12px; text-align: center;">Cantidad (Unidades)</th>
                        </tr>
                    </thead>
                    <tbody>
    `;
    
    let totalUnidades = 0;
    for (const item of productos) {
        const cantidad = item.unidades_vendidas || 0;
        totalUnidades += cantidad;
        html += `
            <tr style="border-bottom: 1px solid #eee;">
                <td style="padding: 10px 12px;">${item.producto}</td>
                <td style="padding: 10px 12px; text-align: center; font-weight: bold; color: #1976D2;">${cantidad}</td>
            </tr>
        `;
    }
    
    html += `
                    </tbody>
                </table>
            </div>
            <div style="margin-top: 16px; text-align: center; color: #666;">
                Total de productos vendidos: ${totalUnidades} unidades
            </div>
        </div>
    `;
    
    const container = document.getElementById('reporte_resultados');
    container.insertAdjacentHTML('beforeend', html);
}

function limpiarFiltros() {
    document.getElementById('fecha_inicio').value = '';
    document.getElementById('fecha_fin').value = '';
    document.getElementById('reporte_tipo').value = 'dia';
    document.getElementById('tipo_venta').value = 'todas';
    document.getElementById('reporte_resultados').innerHTML = '<div style="text-align:center; color:#999;">Seleccione un tipo de reporte y un rango de fechas</div>';
}

function setupReportesListeners() {
    const btnAplicar = document.getElementById('btn_aplicar_filtros');
    const btnLimpiar = document.getElementById('btn_limpiar_filtros');
    
    if (btnAplicar) {
        btnAplicar.addEventListener('click', () => {
            cargarReportesConFiltros();
        });
    }
    
    if (btnLimpiar) {
        btnLimpiar.addEventListener('click', () => {
            limpiarFiltros();
        });
    }
}

// ========== BUSCADOR DE CLIENTES ==========
let timeoutBusqueda = null;

async function buscarClientes(texto) {
    if (!texto || texto.length < 2) {
        document.getElementById('resultado_busqueda').style.display = 'none';
        return;
    }
    
    try {
        const response = await fetch(`/api/clientes/buscar?nombre=${encodeURIComponent(texto)}`);
        const clientes = await response.json();
        
        const resultadosDiv = document.getElementById('resultado_busqueda');
        
        if (clientes && clientes.length > 0) {
            resultadosDiv.innerHTML = clientes.map(cliente => `
                <div class="busqueda-item" onclick="seleccionarClienteBusqueda(${cliente.id}, '${escapeHtml(cliente.nombre)}')">
                    <strong>${escapeHtml(cliente.nombre)}</strong>
                    <small>📞 ${cliente.telefono || 'Sin teléfono'}</small>
                </div>
            `).join('');
            resultadosDiv.style.display = 'block';
        } else {
            resultadosDiv.innerHTML = '<div class="busqueda-item">No se encontraron clientes</div>';
            resultadosDiv.style.display = 'block';
        }
    } catch (error) {
        console.error('Error buscando clientes:', error);
    }
}

function seleccionarClienteBusqueda(id, nombre) {
    const select = document.getElementById('venta_cliente');
    if (select) {
        select.value = id;
        showToast(`Cliente seleccionado: ${nombre}`);
    }
    document.getElementById('buscar_cliente').value = '';
    document.getElementById('resultado_busqueda').style.display = 'none';
}

document.addEventListener('click', function(e) {
    const resultadosDiv = document.getElementById('resultado_busqueda');
    const inputBusqueda = document.getElementById('buscar_cliente');
    if (resultadosDiv && inputBusqueda && !inputBusqueda.contains(e.target) && !resultadosDiv.contains(e.target)) {
        resultadosDiv.style.display = 'none';
    }
});

// ========== NAVEGACIÓN ==========
function setupNavigation() {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => {
            const tabName = item.dataset.tab;
            document.querySelectorAll('.nav-item').forEach(nav => nav.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
            item.classList.add('active');
            document.getElementById(`tab-${tabName}`).classList.add('active');
            
            if (tabName === 'clientes') cargarClientes();
            if (tabName === 'productos') cargarProductos();
            if (tabName === 'creditos') {
                cargarCreditosAgrupados();
                cargarClientesHistorial();
                cargarProductosHistorial();
            }
            if (tabName === 'reportes') cargarReportes('semanal');
        });
    });
}

function setupEventListeners() {
    document.getElementById('btn_agregar_cliente')?.addEventListener('click', agregarCliente);
    document.getElementById('btn_agregar_producto')?.addEventListener('click', agregarProducto);
    document.getElementById('btn_agregar_al_carrito')?.addEventListener('click', agregarAlCarrito);
    document.getElementById('btn_registrar_venta_multiple')?.addEventListener('click', registrarVentaMultiple);
    document.getElementById('btn_enviar_recordatorios')?.addEventListener('click', enviarRecordatorios);
    document.getElementById('btn_agregar_producto_historial')?.addEventListener('click', agregarProductoHistorial);
    document.getElementById('btn_guardar_venta_historica')?.addEventListener('click', guardarVentaHistorica);
    document.getElementById('historial_producto')?.addEventListener('change', calcularPreviewHistorial);
    document.getElementById('historial_cantidad')?.addEventListener('input', calcularPreviewHistorial);
    document.getElementById('historial_tasa')?.addEventListener('input', calcularPreviewHistorial);
    document.getElementById('historial_cliente')?.addEventListener('change', calcularPreviewHistorial);
    document.getElementById('refreshBtn')?.addEventListener('click', () => {
        cargarTasa();
        cargarProductos();
        cargarClientes();
        cargarCreditosAgrupados();
        showToast('Actualizado');
    });
    
    document.getElementById('buscar_cliente')?.addEventListener('input', (e) => {
        clearTimeout(timeoutBusqueda);
        timeoutBusqueda = setTimeout(() => {
            buscarClientes(e.target.value);
        }, 300);
    });
    
    document.querySelectorAll('[data-reporte]').forEach(btn => {
        btn.addEventListener('click', () => {
            cargarReportes(btn.dataset.reporte);
        });
    });

    document.getElementById('buscar_producto_nombre')?.addEventListener('input', (e) => {
        clearTimeout(timeoutBusqueda);
        timeoutBusqueda = setTimeout(() => {
            buscarProductoPorNombre();
        }, 300);
    });

    document.getElementById('btn_actualizar_producto')?.addEventListener('click', actualizarProducto);
    document.getElementById('btn_cancelar_modificar')?.addEventListener('click', cancelarModificarProducto);

    document.getElementById('buscar_cliente_nombre')?.addEventListener('input', (e) => {
        clearTimeout(timeoutBusqueda);
        timeoutBusqueda = setTimeout(() => {
            buscarClientePorNombre();
        }, 300);
    });

    document.getElementById('btn_actualizar_cliente')?.addEventListener('click', actualizarCliente);
    document.getElementById('btn_cancelar_modificar_cliente')?.addEventListener('click', cancelarModificarCliente);
}

// ========== MODAL DE RECIBO ==========
let base64ReciboActual = null;
let nombreReciboActual = '';

async function abrirReciboEnModal(blob, nombreArchivo) {
    nombreReciboActual = nombreArchivo;
    const reader = new FileReader();
    reader.onloadend = function() {
        base64ReciboActual = reader.result;
        const img = document.getElementById('img_recibo');
        img.src = base64ReciboActual;
        const modal = document.getElementById('modalRecibo');
        modal.style.display = 'flex';
    };
    reader.readAsDataURL(blob);
}

function cerrarModalRecibo() {
    const modal = document.getElementById('modalRecibo');
    modal.style.display = 'none';
    document.getElementById('img_recibo').src = '';
    base64ReciboActual = null;
}

async function descargarRecibo() {
    if (base64ReciboActual) {
        const link = document.createElement('a');
        link.href = base64ReciboActual;
        link.download = nombreReciboActual;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        showToast('✅ Archivo descargado');
    } else {
        showToast('No hay recibo para descargar');
    }
}

async function compartirRecibo() {
    if (!base64ReciboActual) {
        showToast('No hay recibo para compartir');
        return;
    }
    
    if (navigator.share && /Mobi|Android|iPhone|iPad|iPod/i.test(navigator.userAgent)) {
        try {
            const blob = await (await fetch(base64ReciboActual)).blob();
            const file = new File([blob], nombreReciboActual, { type: 'image/png' });
            await navigator.share({
                title: 'Recibo Ventas Pro',
                text: 'Adjunto recibo de pago',
                files: [file]
            });
            showToast('📤 Compartido exitosamente');
        } catch (error) {
            if (error.name !== 'AbortError') {
                console.error('Error al compartir:', error);
                showToast('Error al compartir, prueba descargando primero');
            }
        }
    } else {
        showToast('Compartir no disponible, descargando archivo');
        descargarRecibo();
    }
}

setTimeout(() => {
    const btnDescargar = document.getElementById('btn_descargar_recibo');
    const btnCompartir = document.getElementById('btn_compartir_recibo');
    if (btnDescargar) btnDescargar.addEventListener('click', descargarRecibo);
    if (btnCompartir) btnCompartir.addEventListener('click', compartirRecibo);
}, 100);

// ========== GRÁFICOS DE VENTAS ==========
let chartVentas = null;

// ========== GRÁFICOS DE VENTAS ==========
async function cargarGrafico() {
    const fechaInicio = document.getElementById('fecha_inicio').value;
    const fechaFin = document.getElementById('fecha_fin').value;
    
    if (!fechaInicio || !fechaFin) {
        showToast('Seleccione ambas fechas para el gráfico');
        return;
    }
    
    showLoading();
    
    try {
        const response = await fetch('/api/reportes/rango', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                fecha_inicio: fechaInicio,
                fecha_fin: fechaFin,
                tipo: 'productos',
                filtro_venta: 'todas'
            })
        });
        const result = await response.json();
        hideLoading();
        
        if (!result.success || !result.data || result.data.length === 0) {
            showToast('No hay datos para el gráfico en este rango');
            return;
        }
        
        // Eliminar gráfico anterior si existe
        const graficoExistente = document.querySelector('.grafico-tabla');
        if (graficoExistente) graficoExistente.remove();
        
        const productos = [...result.data].sort((a, b) => (b.unidades_vendidas || 0) - (a.unidades_vendidas || 0));
        
        let html = `
            <div class="grafico-tabla" style="background: white; border-radius: 12px; padding: 16px; margin-top: 20px;">
                <h4 style="color: #1976D2; margin-bottom: 16px;">📊 Productos más vendidos</h4>
                <div style="overflow-x: auto;">
                    <table style="width: 100%; border-collapse: collapse;">
                        <thead>
                            <tr style="background: #1976D2; color: white;">
                                <th style="padding: 12px; text-align: left;">Producto</th>
                                <th style="padding: 12px; text-align: center;">Cantidad (Unidades)</th>
                            </tr>
                        </thead>
                        <tbody>
        `;
        
        let totalUnidades = 0;
        for (const item of productos) {
            const cantidad = item.unidades_vendidas || 0;
            totalUnidades += cantidad;
            html += `
                <tr style="border-bottom: 1px solid #eee;">
                    <td style="padding: 10px 12px;">${item.producto}</td>
                    <td style="padding: 10px 12px; text-align: center; font-weight: bold; color: #1976D2;">${cantidad}</td>
                </tr>
            `;
        }
        
        html += `
                        </tbody>
                    </table>
                </div>
                <div style="margin-top: 16px; text-align: center; color: #666;">
                    Total de productos vendidos: ${totalUnidades} unidades
                </div>
            </div>
        `;
        
        const container = document.getElementById('reporte_resultados');
        container.insertAdjacentHTML('beforeend', html);
        showToast('✅ Gráfico actualizado');
        
    } catch (error) {
        hideLoading();
        console.error('Error:', error);
        showToast('Error al cargar el gráfico');
    }
}

function setupGraficoListeners() {
    const btnGrafico = document.getElementById('btn_actualizar_grafico');
    if (btnGrafico) {
        btnGrafico.addEventListener('click', cargarGrafico);
    }
}



// ========== FUNCIONES GLOBALES ==========
window.mostrarModalReponer = function(id, descripcion, costo) {
    const cantidad = prompt(`Reponer stock de: ${descripcion}\nCosto actual: $${costo}\n\nIngrese la cantidad a agregar:`);
    if (cantidad && parseInt(cantidad) > 0) {
        fetch(`/api/productos/reponer/${id}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ cantidad: parseInt(cantidad), costo: costo })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                showToast(`✅ Stock actualizado: +${cantidad} unidades`);
                cargarProductos();
            } else {
                showToast('❌ Error al reponer stock');
            }
        });
    }
};

window.cerrarModalPago = function() {
    const modal = document.getElementById('modal-pago-parcial');
    if (modal) modal.style.display = 'none';
};

window.confirmarPagoParcial = function() {
    showToast('Usa el botón Pagar en la lista de créditos');
};

// ========== INIT ==========
async function init() {
    await cargarTasa();
    await cargarClientes();
    await cargarProductos();
    await cargarCreditosAgrupados();
    await cargarClientesHistorial();
    await cargarProductosHistorial();
    setupNavigation();
    setupEventListeners();
    setupReportesListeners();
    setupGraficoListeners();
    cargarReportes('semanal');
    setInterval(cargarTasa, 300000);
}

document.addEventListener('DOMContentLoaded', init);